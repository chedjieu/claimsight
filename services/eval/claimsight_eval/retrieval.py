"""Retrieval helpers used by gold-set tests."""

from __future__ import annotations

from claimsight_graphrag.data import DEMO_CLAIMS
from claimsight_graphrag.retriever import HybridRetriever
from claimsight_graphrag.store import MemoryGraphStore


def vector_misses_step_therapy() -> tuple[bool, bool]:
    """Vector-only lacks the prior metformin failure; hybrid includes it."""
    store = MemoryGraphStore()
    retriever = HybridRetriever(store)
    claim = DEMO_CLAIMS["step_therapy"]
    vec = retriever.vector_only(claim)
    hyb = retriever.retrieve(claim)
    vec_has_prior = any(
        c.get("kind") == "prior_claim" or c.get("id") == "CLM-PRIOR-MET"
        for c in vec.get("citations") or []
    )
    hyb_has_prior = any(
        (c.get("kind") == "prior_claim") or c.get("id") == "CLM-PRIOR-MET"
        for c in hyb.get("citations") or []
    ) or bool(hyb.get("failed_steps"))
    return vec_has_prior, hyb_has_prior
