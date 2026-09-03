"""Graph stores: in-memory (CI / no Docker) and optional Neo4j."""

from __future__ import annotations

import logging
import os
import re
from collections import defaultdict
from typing import Any, Protocol

from claimsight_graphrag.data import (
    DEMO_CLAIMS,
    DIAGNOSES,
    GUIDELINES,
    PASSAGES,
    PATIENTS,
    POLICY_CLAUSES,
    PRIOR_CLAIMS,
    PROCEDURES,
    PROVIDERS,
)

log = logging.getLogger(__name__)


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class GraphStore(Protocol):
    def seed(self) -> None: ...
    def upsert_claim(self, claim: dict[str, Any]) -> None: ...
    def subgraph_for_claim(self, claim: dict[str, Any]) -> dict[str, Any]: ...
    def vector_search(self, query: str, k: int = 6) -> list[dict[str, Any]]: ...
    def patient_history(self, patient_id: str) -> list[dict[str, Any]]: ...
    def provider_stats(self, provider_id: str) -> dict[str, Any]: ...
    def record_decision(self, claim_id: str, action: str, actor: str, reason: str | None = None) -> None: ...
    def delete_claim(self, claim_id: str) -> None: ...
    def kind(self) -> str: ...


class MemoryGraphStore:
    """Laptop/CI source of truth. Same schema as Neo4j seed."""

    def __init__(self) -> None:
        self.patients = {p["id"]: dict(p) for p in PATIENTS}
        self.providers = {p["id"]: dict(p) for p in PROVIDERS}
        self.diagnoses = {d["id"]: dict(d) for d in DIAGNOSES}
        self.procedures = {p["id"]: dict(p) for p in PROCEDURES}
        self.policies = {p["id"]: dict(p) for p in POLICY_CLAUSES}
        self.guidelines = {g["id"]: dict(g) for g in GUIDELINES}
        self.passages = list(PASSAGES)
        self.claims: dict[str, dict[str, Any]] = {}
        self.decisions: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.by_patient: dict[str, list[str]] = defaultdict(list)
        self.by_provider: dict[str, list[str]] = defaultdict(list)
        self.seed()

    def kind(self) -> str:
        return "memory"

    def seed(self) -> None:
        for c in PRIOR_CLAIMS:
            self.upsert_claim(c)

    def upsert_claim(self, claim: dict[str, Any]) -> None:
        cid = claim["id"]
        self.claims[cid] = dict(claim)
        self.by_patient[claim["patient_id"]].append(cid)
        self.by_provider[claim["provider_id"]].append(cid)

    def patient_history(self, patient_id: str) -> list[dict[str, Any]]:
        return [self.claims[i] for i in self.by_patient.get(patient_id, []) if i in self.claims]

    def provider_stats(self, provider_id: str) -> dict[str, Any]:
        rows = [self.claims[i] for i in self.by_provider.get(provider_id, []) if i in self.claims]
        amounts = [float(r.get("amount_usd") or 0) for r in rows]
        prov = self.providers.get(provider_id) or {}
        return {
            "provider_id": provider_id,
            "claim_count": len(rows),
            "mean_amount": sum(amounts) / len(amounts) if amounts else 0,
            "outlier_score": float(prov.get("outlier_score") or 0),
            "watchlist": prov.get("classification") == "watchlist",
        }

    def vector_search(self, query: str, k: int = 6) -> list[dict[str, Any]]:
        q = _tokens(query)
        scored = []
        for p in self.passages:
            score = _jaccard(q, _tokens(p["text"] + " " + p.get("kind", "")))
            scored.append((score, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        out = []
        for score, p in scored[:k]:
            if score <= 0:
                continue
            item = dict(p)
            item["score"] = round(score, 4)
            out.append(item)
        return out or [dict(scored[0][1], score=0.0)] if scored else []

    def subgraph_for_claim(self, claim: dict[str, Any]) -> dict[str, Any]:
        pid = claim.get("patient_id")
        prid = claim.get("provider_id")
        icd = list(claim.get("icd10") or [])
        cpt = list(claim.get("cpt") or [])
        history = [h for h in self.patient_history(pid) if h["id"] != claim.get("id")]
        policies = [
            p
            for p in self.policies.values()
            if set(p.get("procedure_ids") or []) & set(cpt)
            or set(p.get("diagnosis_ids") or []) & set(icd)
            or p["id"] == "POL-HIGH-VALUE"
        ]
        guidelines = [
            g
            for g in self.guidelines.values()
            if set(g.get("diagnosis_ids") or []) & set(icd)
        ]
        failed_steps = [
            h
            for h in history
            if h.get("outcome") in {"failed_therapy", "failed_conservative"}
        ]
        return {
            "patient": {k: v for k, v in (self.patients.get(pid) or {}).items() if k != "ssn"},
            "provider": self.providers.get(prid) or {},
            "diagnoses": [self.diagnoses[i] for i in icd if i in self.diagnoses],
            "procedures": [self.procedures[i] for i in cpt if i in self.procedures],
            "history": history,
            "failed_steps": failed_steps,
            "policies": policies,
            "guidelines": guidelines,
            "provider_stats": self.provider_stats(prid),
        }

    def record_decision(
        self, claim_id: str, action: str, actor: str, reason: str | None = None
    ) -> None:
        self.decisions[claim_id].append(
            {"claim_id": claim_id, "action": action, "actor": actor, "reason": reason}
        )

    def delete_claim(self, claim_id: str) -> None:
        claim = self.claims.pop(claim_id, None)
        if not claim:
            return
        pid = claim.get("patient_id")
        prid = claim.get("provider_id")
        if pid and claim_id in self.by_patient.get(pid, []):
            self.by_patient[pid] = [i for i in self.by_patient[pid] if i != claim_id]
        if prid and claim_id in self.by_provider.get(prid, []):
            self.by_provider[prid] = [i for i in self.by_provider[prid] if i != claim_id]
        self.decisions.pop(claim_id, None)


def _parse_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.startswith("["):
        import json

        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:  # noqa: BLE001
            return []
    return []


class Neo4jGraphStore:
    def __init__(self, uri: str, user: str, password: str) -> None:
        from neo4j import GraphDatabase

        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self._memory = MemoryGraphStore()

    def kind(self) -> str:
        return "neo4j"

    def seed(self) -> None:
        self._memory.seed()
        try:
            with self._driver.session() as s:
                s.run("MATCH (n) DETACH DELETE n")
                for p in PATIENTS:
                    s.run(
                        "MERGE (x:Patient {id:$id}) SET x.name=$name, x.mrn=$mrn",
                        id=p["id"],
                        name=p["name"],
                        mrn=p["mrn"],
                    )
                for p in PROVIDERS:
                    s.run(
                        "MERGE (x:Provider {id:$id}) SET x.name=$name, x.specialty=$specialty",
                        id=p["id"],
                        name=p["name"],
                        specialty=p["specialty"],
                    )
                for d in DIAGNOSES:
                    s.run(
                        "MERGE (x:Diagnosis {id:$id}) SET x.name=$name, x.sensitive=$sensitive",
                        **d,
                    )
                for p in PROCEDURES:
                    s.run(
                        "MERGE (x:Procedure {id:$id}) SET x.name=$name, x.category=$category",
                        **p,
                    )
                for p in POLICY_CLAUSES:
                    s.run(
                        "MERGE (x:PolicyClause {id:$id}) SET x.title=$title, x.text=$text",
                        id=p["id"],
                        title=p["title"],
                        text=p["text"],
                    )
                    for proc in p.get("procedure_ids") or []:
                        s.run(
                            "MATCH (pr:Procedure {id:$pid}), (po:PolicyClause {id:$oid}) "
                            "MERGE (pr)-[:REQUIRES]->(po)",
                            pid=proc,
                            oid=p["id"],
                        )
                    for dx in p.get("diagnosis_ids") or []:
                        s.run(
                            "MATCH (d:Diagnosis {id:$did}), (po:PolicyClause {id:$oid}) "
                            "MERGE (d)-[:GOVERNED_BY]->(po)",
                            did=dx,
                            oid=p["id"],
                        )
                for g in GUIDELINES:
                    s.run(
                        "MERGE (x:Guideline {id:$id}) SET x.title=$title, x.text=$text",
                        id=g["id"],
                        title=g["title"],
                        text=g["text"],
                    )
                    for dx in g.get("diagnosis_ids") or []:
                        s.run(
                            "MATCH (d:Diagnosis {id:$did}), (g:Guideline {id:$gid}) "
                            "MERGE (d)-[:GOVERNED_BY]->(g)",
                            did=dx,
                            gid=g["id"],
                        )
                for c in PRIOR_CLAIMS:
                    self._write_claim(s, c)
        except Exception as exc:  # noqa: BLE001
            log.warning("Neo4j seed failed, memory remains source of truth: %s", exc)

    def _write_claim(self, s: Any, claim: dict[str, Any]) -> None:
        import json

        s.run(
            "MERGE (c:Claim {id:$id}) SET c.amount=$amount, c.date=$date, c.outcome=$outcome, "
            "c.cpt=$cpt, c.icd10=$icd10, c.patient_id=$patient_id, c.provider_id=$provider_id",
            id=claim["id"],
            amount=claim.get("amount_usd"),
            date=claim.get("service_date"),
            outcome=claim.get("outcome"),
            cpt=json.dumps(claim.get("cpt") or []),
            icd10=json.dumps(claim.get("icd10") or []),
            patient_id=claim.get("patient_id"),
            provider_id=claim.get("provider_id"),
        )
        s.run(
            "MATCH (p:Patient {id:$pid}), (c:Claim {id:$cid}) MERGE (p)-[:HAS_CLAIM]->(c)",
            pid=claim["patient_id"],
            cid=claim["id"],
        )
        s.run(
            "MATCH (pr:Provider {id:$pid}), (c:Claim {id:$cid}) MERGE (pr)-[:BILLED]->(c)",
            pid=claim["provider_id"],
            cid=claim["id"],
        )
        for dx in claim.get("icd10") or []:
            s.run(
                "MATCH (p:Patient {id:$pid}), (d:Diagnosis {id:$did}) "
                "MERGE (p)-[:HAS_DIAGNOSIS]->(d) "
                "WITH d MATCH (c:Claim {id:$cid}) MERGE (c)-[:FOR_DIAGNOSIS]->(d)",
                pid=claim["patient_id"],
                did=dx,
                cid=claim["id"],
            )
        for proc in claim.get("cpt") or []:
            s.run(
                "MATCH (c:Claim {id:$cid}), (pr:Procedure {id:$proc}) "
                "MERGE (c)-[:FOR_PROCEDURE]->(pr)",
                cid=claim["id"],
                proc=proc,
            )

    def upsert_claim(self, claim: dict[str, Any]) -> None:
        self._memory.upsert_claim(claim)
        try:
            with self._driver.session() as s:
                self._write_claim(s, claim)
        except Exception as exc:  # noqa: BLE001
            log.debug("Neo4j upsert skipped: %s", exc)

    def subgraph_for_claim(self, claim: dict[str, Any]) -> dict[str, Any]:
        mem = self._memory.subgraph_for_claim(claim)
        try:
            history = self._cypher_history(
                str(claim.get("patient_id") or ""), str(claim.get("id") or "")
            )
            if history:
                mem["history"] = history
                mem["failed_steps"] = [
                    h
                    for h in history
                    if h.get("outcome") in {"failed_therapy", "failed_conservative"}
                ]
            stats = self._cypher_provider_stats(str(claim.get("provider_id") or ""))
            if stats.get("claim_count"):
                mem["provider_stats"] = {**(mem.get("provider_stats") or {}), **stats}
        except Exception as exc:  # noqa: BLE001
            log.debug("Neo4j subgraph read fell back to memory: %s", exc)
        return mem

    def _cypher_history(self, patient_id: str, claim_id: str) -> list[dict[str, Any]]:
        with self._driver.session() as s:
            rows = s.run(
                "MATCH (p:Patient {id:$pid})-[:HAS_CLAIM]->(c:Claim) "
                "WHERE c.id <> $cid "
                "RETURN c.id AS id, c.date AS service_date, c.amount AS amount_usd, "
                "c.outcome AS outcome, c.cpt AS cpt, c.icd10 AS icd10, "
                "c.patient_id AS patient_id, c.provider_id AS provider_id",
                pid=patient_id,
                cid=claim_id,
            )
            out = []
            for r in rows:
                out.append(
                    {
                        "id": r["id"],
                        "patient_id": r["patient_id"] or patient_id,
                        "provider_id": r["provider_id"],
                        "service_date": r["service_date"],
                        "amount_usd": r["amount_usd"],
                        "outcome": r["outcome"],
                        "cpt": _parse_list(r["cpt"]),
                        "icd10": _parse_list(r["icd10"]),
                    }
                )
            return out

    def _cypher_provider_stats(self, provider_id: str) -> dict[str, Any]:
        with self._driver.session() as s:
            rec = s.run(
                "MATCH (pr:Provider {id:$pid})-[:BILLED]->(c:Claim) "
                "RETURN count(c) AS n, avg(c.amount) AS mean_amount",
                pid=provider_id,
            ).single()
        if not rec:
            return {}
        return {
            "provider_id": provider_id,
            "claim_count": int(rec["n"] or 0),
            "mean_amount": float(rec["mean_amount"] or 0),
        }

    def vector_search(self, query: str, k: int = 6) -> list[dict[str, Any]]:
        return self._memory.vector_search(query, k)

    def patient_history(self, patient_id: str) -> list[dict[str, Any]]:
        try:
            rows = self._cypher_history(patient_id, "")
            if rows:
                return rows
        except Exception as exc:  # noqa: BLE001
            log.debug("Neo4j history read fell back to memory: %s", exc)
        return self._memory.patient_history(patient_id)

    def provider_stats(self, provider_id: str) -> dict[str, Any]:
        mem = self._memory.provider_stats(provider_id)
        try:
            cypher = self._cypher_provider_stats(provider_id)
            if cypher.get("claim_count"):
                return {**mem, **cypher}
        except Exception as exc:  # noqa: BLE001
            log.debug("Neo4j stats read fell back to memory: %s", exc)
        return mem

    def record_decision(
        self, claim_id: str, action: str, actor: str, reason: str | None = None
    ) -> None:
        self._memory.record_decision(claim_id, action, actor, reason)
        did = f"DEC-{claim_id}-{action}"
        try:
            with self._driver.session() as s:
                s.run(
                    "MERGE (d:Decision {id:$id}) "
                    "SET d.action=$action, d.actor=$actor, d.reason=$reason "
                    "WITH d MATCH (c:Claim {id:$cid}) MERGE (d)-[:MADE_FOR]->(c)",
                    id=did,
                    action=action,
                    actor=actor,
                    reason=reason or "",
                    cid=claim_id,
                )
        except Exception as exc:  # noqa: BLE001
            log.debug("Neo4j decision write skipped: %s", exc)

    def delete_claim(self, claim_id: str) -> None:
        self._memory.delete_claim(claim_id)
        try:
            with self._driver.session() as s:
                s.run(
                    "MATCH (d:Decision)-[:MADE_FOR]->(c:Claim {id:$id}) DETACH DELETE d",
                    id=claim_id,
                )
                s.run("MATCH (c:Claim {id:$id}) DETACH DELETE c", id=claim_id)
        except Exception as exc:  # noqa: BLE001
            log.debug("Neo4j claim delete skipped: %s", exc)


_STORE: GraphStore | None = None


def get_store() -> GraphStore:
    global _STORE
    if _STORE is not None:
        return _STORE
    uri = os.getenv("NEO4J_URI", "")
    if uri.startswith("bolt://") and os.getenv("CLAIMSIGHT_FORCE_MEMORY") != "1":
        try:
            store = Neo4jGraphStore(
                uri,
                os.getenv("NEO4J_USER", "neo4j"),
                os.getenv("NEO4J_PASSWORD", "claimsight-dev"),
            )
            store.seed()
            _STORE = store
            return _STORE
        except Exception as exc:  # noqa: BLE001
            log.warning("Neo4j unavailable (%s); using MemoryGraphStore", exc)
    _STORE = MemoryGraphStore()
    return _STORE


def reset_store() -> GraphStore:
    global _STORE
    _STORE = MemoryGraphStore()
    return _STORE


def demo_payload(name: str) -> dict[str, Any]:
    return dict(DEMO_CLAIMS[name])
