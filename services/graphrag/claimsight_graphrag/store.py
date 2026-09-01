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
        s.run(
            "MERGE (c:Claim {id:$id}) SET c.amount=$amount, c.date=$date, c.outcome=$outcome",
            id=claim["id"],
            amount=claim.get("amount_usd"),
            date=claim.get("service_date"),
            outcome=claim.get("outcome"),
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
        return self._memory.subgraph_for_claim(claim)

    def vector_search(self, query: str, k: int = 6) -> list[dict[str, Any]]:
        return self._memory.vector_search(query, k)

    def patient_history(self, patient_id: str) -> list[dict[str, Any]]:
        return self._memory.patient_history(patient_id)

    def provider_stats(self, provider_id: str) -> dict[str, Any]:
        return self._memory.provider_stats(provider_id)


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
