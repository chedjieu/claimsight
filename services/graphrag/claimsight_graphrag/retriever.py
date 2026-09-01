"""Hybrid GraphRAG: graph traversal for precedent facts + token/vector search for guidelines."""

from __future__ import annotations

from typing import Any

from claimsight_graphrag.store import GraphStore


class HybridRetriever:
    def __init__(self, store: GraphStore) -> None:
        self.store = store

    def vector_only(self, claim: dict[str, Any], k: int = 6) -> dict[str, Any]:
        query = " ".join(
            [
                " ".join(claim.get("icd10") or []),
                " ".join(claim.get("cpt") or []),
                claim.get("notes") or "",
                "policy coverage step therapy medical necessity guideline",
            ]
        )
        passages = self.store.vector_search(query, k=k)
        citations = [
            {
                "id": p["id"],
                "kind": p.get("kind"),
                "entity_id": p.get("entity_id"),
                "text": p.get("text", "")[:800],
                "source": "vector",
                "score": p.get("score"),
            }
            for p in passages
        ]
        return {
            "mode": "vector",
            "passages": passages,
            "citations": citations,
            "history": [],
            "failed_steps": [],
            "policies": [],
            "guidelines": [],
        }

    def retrieve(self, claim: dict[str, Any], k: int = 6) -> dict[str, Any]:
        subgraph = self.store.subgraph_for_claim(claim)
        query = " ".join(
            [
                " ".join(claim.get("icd10") or []),
                " ".join(claim.get("cpt") or []),
                " ".join(p.get("title", "") for p in subgraph.get("policies") or []),
                claim.get("notes") or "",
            ]
        )
        passages = self.store.vector_search(query, k=k)
        citations = []
        for p in passages:
            citations.append(
                {
                    "id": p["id"],
                    "kind": p.get("kind"),
                    "entity_id": p.get("entity_id"),
                    "text": p.get("text", "")[:800],
                    "source": "vector",
                    "score": p.get("score"),
                }
            )
        for pol in subgraph.get("policies") or []:
            citations.append(
                {
                    "id": pol["id"],
                    "kind": "policy",
                    "entity_id": pol["id"],
                    "text": pol.get("text", "")[:800],
                    "source": "graph",
                }
            )
        for h in subgraph.get("failed_steps") or []:
            citations.append(
                {
                    "id": h["id"],
                    "kind": "prior_claim",
                    "entity_id": h["id"],
                    "text": (
                        f"Prior {h.get('cpt')} on {h.get('service_date')} "
                        f"outcome={h.get('outcome')}: {h.get('notes', '')}"
                    )[:800],
                    "source": "graph",
                }
            )
        seen: set[str] = set()
        uniq = []
        for c in citations:
            if c["id"] in seen:
                continue
            seen.add(c["id"])
            uniq.append(c)
        subgraph["citations"] = uniq
        subgraph["passages"] = passages
        subgraph["mode"] = "hybrid"
        return subgraph
