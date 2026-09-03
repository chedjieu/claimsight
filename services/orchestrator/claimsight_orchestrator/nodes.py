"""Specialist nodes — independently testable; graph wires them."""

from __future__ import annotations

import json
import os

from claimsight_graphrag.retriever import HybridRetriever
from claimsight_orchestrator.acl import assert_tool_allowed
from claimsight_orchestrator.llm import complete_json, estimate_tokens
from claimsight_orchestrator.qa import should_qa_sample
from claimsight_orchestrator.state import ClaimState
from claimsight_phi_guard.phi import PhiGuard
from claimsight_prompts import COMPLIANCE, FRAUD, NECESSITY, POLICY, SUPERVISOR
from claimsight_schemas.models import AgentFinding, Citation

REDACTOR = PhiGuard()
HIGH_VALUE = float(os.getenv("CLAIMSIGHT_HIGH_VALUE_USD", "50000"))
SENSITIVE_DX = {"F32.1", "F32.0", "F32.2"}


def _bump(state: ClaimState, *parts: str) -> None:
    state.token_used += estimate_tokens(*parts)
    if state.token_used > state.token_budget:
        state.cost_capped = True


def intake_node(state: ClaimState) -> ClaimState:
    assert_tool_allowed("intake", "redact")
    claim = state.claim
    notes = claim.get("notes") or ""
    docs = [d.get("text") if isinstance(d, dict) else str(d) for d in claim.get("documents") or []]
    blob = notes + "\n" + "\n".join(docs)
    result = REDACTOR.redact_text(blob)
    state.redacted_notes = result.text
    state.redacted_docs = [REDACTOR.redact_text(d).text for d in docs]
    state.phi_mapping = result.mapping
    state.phi_findings = result.findings
    extra = []
    for d in docs:
        extra.extend(REDACTOR.redact_text(d).injection_hits)
    state.injection_hits = list({*result.injection_hits, *extra})
    state.tools_used.setdefault("intake", []).append("redact")
    state.traces["intake"] = (
        f"redacted findings={state.phi_findings} injection={bool(state.injection_hits)}"
    )
    _bump(state, blob)
    return state


def coding_node(state: ClaimState, retriever: HybridRetriever) -> ClaimState:
    assert_tool_allowed("coding", "write_graph")
    retriever.store.upsert_claim(state.claim)
    state.tools_used.setdefault("coding", []).append("write_graph")
    state.traces["coding"] = (
        f"upserted {state.claim.get('id')} icd={state.claim.get('icd10')} cpt={state.claim.get('cpt')}"
    )
    _bump(state, json.dumps(state.claim, default=str)[:2000])
    return state


def retrieval_node(state: ClaimState, retriever: HybridRetriever) -> ClaimState:
    assert_tool_allowed("retrieval", "graph_traverse")
    assert_tool_allowed("retrieval", "vector_search")
    retrieved = retriever.retrieve(state.claim)
    state.subgraph = retrieved
    state.citations = [Citation.model_validate(c) for c in retrieved.get("citations") or []]
    state.tools_used.setdefault("retrieval", []).extend(["graph_traverse", "vector_search"])
    state.traces["retrieval"] = (
        f"mode={retrieved.get('mode')} citations={len(state.citations)} "
        f"history={len(retrieved.get('history') or [])} "
        f"failed_steps={len(retrieved.get('failed_steps') or [])}"
    )
    _bump(state, json.dumps(retrieved.get("citations") or [], default=str)[:4000])
    return state


def _cite_ids(state: ClaimState) -> list[str]:
    return [c.id for c in state.citations]


def policy_node(state: ClaimState) -> ClaimState:
    assert_tool_allowed("policy", "graph_traverse")
    policies = state.subgraph.get("policies") or []
    failed = state.subgraph.get("failed_steps") or []
    cpt = set(state.claim.get("cpt") or [])
    amount = float(state.claim.get("amount_usd") or 0)
    step_glp = any(p.get("id") == "POL-STEP-GLP1" for p in policies)
    metformin_failed = any(
        "METF" in (h.get("cpt") or []) and h.get("outcome") == "failed_therapy" for h in failed
    )
    knee_ok = "29881" in cpt and any(p.get("id") == "POL-COVER-KNEE" for p in policies)
    esi_mismatch = "62323" in cpt and "E11.9" in (state.claim.get("icd10") or [])
    verdict = "approve"
    flags: list[str] = []
    if step_glp and not metformin_failed:
        verdict = "deny"
        flags.append("step_therapy_unmet")
    if step_glp and metformin_failed:
        verdict = "approve"
        flags.append("step_therapy_satisfied")
    if esi_mismatch:
        verdict = "deny"
        flags.append("dx_procedure_mismatch")
    if amount >= HIGH_VALUE:
        flags.append("high_value")
    if knee_ok:
        verdict = "approve"
    narrative = (
        f"Policy review for CPT {sorted(cpt)}. "
        + ("Step therapy satisfied via prior metformin failure. " if metformin_failed else "")
        + ("Step therapy unmet. " if "step_therapy_unmet" in flags else "")
        + ("Dx/procedure mismatch. " if esi_mismatch else "")
        + ("High-value threshold exceeded. " if amount >= HIGH_VALUE else "")
    )
    fallback = {
        "verdict": verdict,
        "confidence": 0.86 if flags.count("step_therapy_satisfied") or knee_ok else 0.55,
        "narrative": narrative.strip(),
        "citation_ids": [
            i
            for i in _cite_ids(state)
            if i.startswith("POL") or i.startswith("PAS") or i.startswith("CLM-PRIOR")
        ],
        "flags": flags,
    }
    llm = complete_json(POLICY, json.dumps(REDACTOR.redact_obj(fallback)), fallback)
    llm["flags"] = flags
    llm["verdict"] = verdict
    finding = AgentFinding(
        agent="policy",
        verdict=llm.get("verdict", verdict),
        confidence=float(llm.get("confidence") or fallback["confidence"]),
        narrative=str(llm.get("narrative") or narrative),
        citation_ids=list(llm.get("citation_ids") or fallback["citation_ids"]),
        flags=flags,
        tools_used=["graph_traverse", "vector_search"],
    )
    state.findings.append(finding)
    state.traces["policy"] = finding.narrative[:400]
    _bump(state, finding.narrative)
    return state


def necessity_node(state: ClaimState) -> ClaimState:
    assert_tool_allowed("necessity", "graph_traverse_history")
    assert_tool_allowed("necessity", "vector_search_guidelines")
    failed = state.subgraph.get("failed_steps") or []
    guidelines = state.subgraph.get("guidelines") or []
    cpt = set(state.claim.get("cpt") or [])
    metformin_failed = any(
        "METF" in (h.get("cpt") or []) and h.get("outcome") == "failed_therapy" for h in failed
    )
    pt_failed = any(h.get("outcome") == "failed_conservative" for h in failed)
    esi = "62323" in cpt
    if esi:
        verdict = "deny"
        narrative = "Epidural steroid is not indicated for the billed diagnosis; imaging correlation absent."
        flags = ["not_medically_necessary"]
        conf = 0.8
    elif "J3490" in cpt and metformin_failed:
        verdict = "approve"
        narrative = (
            "ADA-aligned: metformin trial failed; GLP-1 is medically necessary for T2DM with obesity."
        )
        flags = ["history_supports"]
        conf = 0.9
    elif "29881" in cpt and pt_failed:
        verdict = "approve"
        narrative = "AAOS-aligned: displaced meniscal tear after failed conservative care."
        flags = ["history_supports"]
        conf = 0.88
    elif "J3490" in cpt and not metformin_failed:
        verdict = "deny"
        narrative = "No documented first-line failure; medical necessity not established."
        flags = ["missing_step"]
        conf = 0.7
    else:
        verdict = "insufficient"
        narrative = "Guideline match is incomplete; escalate."
        flags = ["insufficient_history"]
        conf = 0.4
    fallback = {
        "verdict": verdict,
        "confidence": conf,
        "narrative": narrative,
        "citation_ids": [g["id"] for g in guidelines] + [h["id"] for h in failed],
        "flags": flags,
    }
    llm = complete_json(NECESSITY, json.dumps(REDACTOR.redact_obj(fallback)), fallback)
    finding = AgentFinding(
        agent="necessity",
        verdict=llm.get("verdict", verdict),
        confidence=float(llm.get("confidence") or conf),
        narrative=str(llm.get("narrative") or narrative),
        citation_ids=list(llm.get("citation_ids") or fallback["citation_ids"]),
        flags=flags,
        tools_used=["graph_traverse_history", "vector_search_guidelines"],
    )
    state.findings.append(finding)
    state.traces["necessity"] = finding.narrative[:400]
    _bump(state, finding.narrative)
    return state


def fraud_node(state: ClaimState) -> ClaimState:
    assert_tool_allowed("fraud", "provider_stats")
    stats = state.subgraph.get("provider_stats") or {}
    amount = float(state.claim.get("amount_usd") or 0)
    cpt = set(state.claim.get("cpt") or [])
    icd = set(state.claim.get("icd10") or [])
    flags: list[str] = []
    if stats.get("watchlist"):
        flags.append("provider_watchlist")
    if stats.get("outlier_score", 0) >= 0.8:
        flags.append("billing_outlier")
    if "62323" in cpt and "E11.9" in icd:
        flags.append("dx_procedure_mismatch")
    if amount >= HIGH_VALUE:
        flags.append("high_value")
    if state.injection_hits:
        flags.append("document_injection")
    verdict = "flag" if flags else "approve"
    narrative = (
        f"Anomaly scan: flags={flags or ['none']}. "
        f"Provider claims={stats.get('claim_count')} outlier={stats.get('outlier_score')}."
    )
    fallback = {
        "verdict": verdict,
        "confidence": 0.92 if flags else 0.75,
        "narrative": narrative,
        "citation_ids": [],
        "flags": flags,
    }
    llm = complete_json(FRAUD, json.dumps(fallback), fallback)
    finding = AgentFinding(
        agent="fraud",
        verdict=llm.get("verdict", verdict),
        confidence=float(llm.get("confidence") or fallback["confidence"]),
        narrative=str(llm.get("narrative") or narrative),
        citation_ids=[],
        flags=flags,
        tools_used=["graph_traverse", "provider_stats"],
    )
    state.findings.append(finding)
    state.traces["fraud"] = finding.narrative[:400]
    _bump(state, finding.narrative)
    return state


def supervisor_node(state: ClaimState) -> ClaimState:
    assert_tool_allowed("supervisor", "synthesize")
    by = {f.agent: f for f in state.findings}
    policy = by.get("policy")
    necessity = by.get("necessity")
    fraud = by.get("fraud")
    amount = float(state.claim.get("amount_usd") or 0)
    icd = set(state.claim.get("icd10") or [])
    flags = []
    for f in state.findings:
        flags.extend(f.flags)
    deny_votes = sum(1 for f in (policy, necessity) if f and f.verdict == "deny")
    approve_votes = sum(1 for f in (policy, necessity) if f and f.verdict == "approve")
    fraud_flag = bool(fraud and (fraud.verdict == "flag" or fraud.flags))
    disagree = deny_votes > 0 and approve_votes > 0
    sensitive = bool(icd & SENSITIVE_DX) or bool(state.claim.get("sensitive_category"))
    rec = "approve"
    if deny_votes and not approve_votes:
        rec = "deny"
    if fraud_flag or disagree or sensitive or amount >= HIGH_VALUE or state.cost_capped:
        rec = "escalate" if rec != "deny" or fraud_flag or disagree else rec
    if fraud_flag and deny_votes:
        rec = "deny"
    if disagree:
        rec = "escalate"
    if state.injection_hits:
        rec = "escalate"
    agreement = 1.0 if (approve_votes == 2 and not fraud_flag) else 0.55 if not disagree else 0.3
    evidence = min(1.0, len(state.citations) / 4)
    conf = round(0.5 * agreement + 0.3 * evidence + 0.2 * (0 if fraud_flag else 0.8), 3)
    if state.cost_capped:
        conf = min(conf, 0.4)
    route = "ready_for_confirmation"
    if (
        conf < 0.7
        or fraud_flag
        or disagree
        or sensitive
        or amount >= HIGH_VALUE
        or rec != "approve"
        or state.injection_hits
        or state.cost_capped
    ):
        route = "pending_human_review"
    if route == "ready_for_confirmation" and should_qa_sample(str(state.claim.get("id") or "")):
        route = "pending_human_review"
        state.qa_sampled = True
        flags.append("qa_sample")
    rationale = (
        f"Supervisor: policy={getattr(policy, 'verdict', None)} "
        f"necessity={getattr(necessity, 'verdict', None)} fraud={getattr(fraud, 'verdict', None)}. "
        f"agreement={agreement} evidence={evidence} flags={flags}. rec={rec} route={route}"
        f"{' qa_sample' if state.qa_sampled else ''}."
    )
    fallback = {
        "recommendation": rec,
        "confidence": conf,
        "rationale": rationale,
        "route": route,
    }
    llm = complete_json(SUPERVISOR, rationale, fallback)
    state.recommendation = str(llm.get("recommendation") or rec)
    state.confidence = float(llm.get("confidence") or conf)
    state.route = str(llm.get("route") or route)
    state.rationale = str(llm.get("rationale") or rationale)
    # Ground routing — never let the model skip HITL on risk
    if route == "pending_human_review":
        state.route = route
    state.traces["supervisor"] = state.rationale[:500]
    _bump(state, state.rationale)
    return state


def compliance_node(state: ClaimState) -> ClaimState:
    assert_tool_allowed("compliance", "scan_leak")
    blob = json.dumps(
        {
            "findings": [f.model_dump() for f in state.findings],
            "rationale": state.rationale,
            "redacted": state.redacted_notes,
        },
        default=str,
    )
    leaks = REDACTOR.scan_for_leak(blob)
    issues = []
    if leaks:
        issues.append(f"phi_leak:{leaks}")
        state.errors.append(f"compliance leak {leaks}")
        state.route = "pending_human_review"
        state.recommendation = "escalate"
    if state.injection_hits:
        issues.append("prompt_injection_in_source")
        state.route = "pending_human_review"
    ungrounded = [
        f.agent
        for f in state.findings
        if f.verdict in {"approve", "deny"} and not f.citation_ids and f.agent != "fraud"
    ]
    if ungrounded:
        issues.append(f"ungrounded:{ungrounded}")
    fallback = {"ok": not issues, "issues": issues, "stripped_flags": leaks}
    llm = complete_json(COMPLIANCE, json.dumps(fallback), fallback)
    state.compliance = llm
    state.traces["compliance"] = json.dumps(llm)[:400]
    _bump(state, blob[:1500])
    return state
