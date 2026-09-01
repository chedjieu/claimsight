from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from claimsight_api.config import settings
from claimsight_api.db import session_scope
from claimsight_api.deps import get_retriever
from claimsight_api.models import AuditEvent, ClaimRow, EvalLabel
from claimsight_orchestrator.graph import run_claim
from claimsight_orchestrator.llm import model_name
from claimsight_storage.object_store import ObjectStore

STORE = ObjectStore()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def audit(actor: str, action: str, entity_id: str, reason: str | None = None, payload: dict | None = None) -> None:
    with session_scope() as db:
        db.add(
            AuditEvent(
                actor=actor,
                action=action,
                entity_type="claim",
                entity_id=entity_id,
                reason=reason,
                payload=json.dumps(payload or {}, default=str),
            )
        )


def ingest_claim(data: dict[str, Any], actor: str = "system") -> str:
    cid = data["id"]
    with session_scope() as db:
        row = db.get(ClaimRow, cid)
        if not row:
            row = ClaimRow(id=cid)
            db.add(row)
        row.patient_id = data.get("patient_id") or ""
        row.provider_id = data.get("provider_id") or ""
        row.icd10 = json.dumps(data.get("icd10") or [])
        row.cpt = json.dumps(data.get("cpt") or [])
        row.amount_usd = float(data.get("amount_usd") or 0)
        row.service_date = data.get("service_date") or ""
        row.notes = data.get("notes") or ""
        row.status = "queued"
        row.ingested_at = _now()
        row.packet_json = json.dumps({"_documents": data.get("documents") or []}, default=str)
    for i, doc in enumerate(data.get("documents") or []):
        text = doc.get("text") if isinstance(doc, dict) else str(doc)
        name = doc.get("filename") if isinstance(doc, dict) else f"doc-{i}.txt"
        STORE.put_bytes(f"{cid}/{name}", (text or "").encode("utf-8"))
    audit(actor, "ingest", cid)
    return cid


def run_and_store(claim_id: str, actor: str = "system") -> str:
    with session_scope() as db:
        row = db.get(ClaimRow, claim_id)
        if not row:
            raise KeyError(claim_id)
        row.status = "processing"
        payload = {
            "id": row.id,
            "patient_id": row.patient_id,
            "provider_id": row.provider_id,
            "icd10": json.loads(row.icd10 or "[]"),
            "cpt": json.loads(row.cpt or "[]"),
            "amount_usd": row.amount_usd,
            "service_date": row.service_date,
            "notes": row.notes,
            "documents": [],
        }
    # re-read docs from notes only if documents not persisted in JSON; attach from original notes
    retriever = get_retriever()
    # documents were stored as objects; reconstruct from notes field for pipeline
    with session_scope() as db:
        row = db.get(ClaimRow, claim_id)
        assert row
        claim = {
            "id": row.id,
            "patient_id": row.patient_id,
            "provider_id": row.provider_id,
            "icd10": json.loads(row.icd10 or "[]"),
            "cpt": json.loads(row.cpt or "[]"),
            "amount_usd": row.amount_usd,
            "service_date": row.service_date,
            "notes": row.notes,
            "documents": [{"filename": "notes.txt", "text": row.notes}],
        }
        # stash extra docs if present in packet placeholder
        extra = json.loads(row.packet_json or "{}").get("_documents")
        if extra:
            claim["documents"] = extra

    state = run_claim(claim, retriever, token_budget=settings.claimsight_token_budget)
    packet = {
        "claim_id": claim_id,
        "recommendation": state.recommendation,
        "confidence": state.confidence,
        "route": state.route,
        "rationale": state.rationale,
        "findings": [f.model_dump() for f in state.findings],
        "citations": [c.model_dump() for c in state.citations],
        "subgraph": _safe_subgraph(state.subgraph),
        "redacted_notes": state.redacted_notes,
        "compliance": state.compliance,
        "traces": state.traces,
        "token_used": state.token_used,
        "token_budget": state.token_budget,
        "cost_capped": state.cost_capped,
        "phi_findings": state.phi_findings,
        "injection_hits": state.injection_hits,
        "model_name": state.model_name,
        "prompt_version": state.prompt_version,
    }
    status = state.route if state.route in {"ready_for_confirmation", "pending_human_review"} else "pending_human_review"
    with session_scope() as db:
        row = db.get(ClaimRow, claim_id)
        assert row
        row.status = status
        row.recommendation = state.recommendation
        row.confidence = state.confidence
        row.route = state.route
        row.packet_json = json.dumps(packet, default=str)
        row.phi_mapping = json.dumps(state.phi_mapping)
        row.model_name = state.model_name
        row.prompt_version = state.prompt_version
        row.token_used = state.token_used
    audit(actor, "orchestrate", claim_id, reason=state.route, payload={"confidence": state.confidence})
    return claim_id


def _safe_subgraph(sub: dict[str, Any]) -> dict[str, Any]:
    """Drop raw PHI fields from the subgraph before persisting the packet."""
    patient = dict(sub.get("patient") or {})
    for k in ("ssn", "email", "mrn", "dob", "address", "name"):
        patient.pop(k, None)
    out = dict(sub)
    out["patient"] = patient
    return out


def decide_claim(
    claim_id: str,
    action: str,
    actor: str,
    reason: str | None = None,
    edited_recommendation: str | None = None,
    edited_narrative: str | None = None,
) -> dict[str, Any]:
    allowed = {"approve", "edit_approve", "override_deny", "escalate"}
    if action not in allowed:
        raise ValueError(f"unknown action {action}")
    with session_scope() as db:
        row = db.get(ClaimRow, claim_id)
        if not row:
            raise KeyError(claim_id)
        if row.status not in {"ready_for_confirmation", "pending_human_review"}:
            raise ValueError(f"claim not awaiting review ({row.status})")
        ai_rec = row.recommendation
        if action == "approve":
            row.status = "approved"
        elif action == "edit_approve":
            row.status = "approved"
            if edited_recommendation:
                row.recommendation = edited_recommendation
            packet = json.loads(row.packet_json or "{}")
            if edited_narrative:
                packet["human_edit"] = edited_narrative
            row.packet_json = json.dumps(packet)
        elif action == "override_deny":
            row.status = "denied"
            row.recommendation = "deny"
        else:
            row.status = "escalated"
        row.decided_by = actor
        row.decided_at = _now()
        override = action in {"edit_approve", "override_deny", "escalate"} or (
            action == "approve" and ai_rec == "deny"
        )
        db.add(
            EvalLabel(
                claim_id=claim_id,
                action=action,
                actor=actor,
                override=override,
                ai_recommendation=ai_rec,
            )
        )
        db.add(
            AuditEvent(
                actor=actor,
                action=f"decide:{action}",
                entity_type="claim",
                entity_id=claim_id,
                reason=reason,
                payload=json.dumps({"ai": ai_rec, "override": override}),
            )
        )
        return {
            "claim_id": claim_id,
            "status": row.status,
            "recommendation": row.recommendation,
            "decided_by": actor,
        }
