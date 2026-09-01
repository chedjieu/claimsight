from __future__ import annotations

from claimsight_eval.retrieval import vector_misses_step_therapy
from claimsight_graphrag.data import DEMO_CLAIMS
from claimsight_graphrag.retriever import HybridRetriever
from claimsight_graphrag.store import MemoryGraphStore


def test_vector_only_misses_prior_metformin_failure():
    vec_has, hyb_has = vector_misses_step_therapy()
    assert vec_has is False
    assert hyb_has is True


def test_hybrid_returns_policy_and_history():
    store = MemoryGraphStore()
    ret = HybridRetriever(store)
    sub = ret.retrieve(DEMO_CLAIMS["step_therapy"])
    ids = {c["id"] for c in sub["citations"]}
    assert "CLM-PRIOR-MET" in ids
    assert any("POL-STEP" in i or i == "PAS-GLP1-STEP" for i in ids)
    assert sub["failed_steps"]


def test_knee_vector_hits_policy():
    store = MemoryGraphStore()
    ret = HybridRetriever(store)
    vec = ret.vector_only(DEMO_CLAIMS["knee"])
    texts = " ".join(c["text"] for c in vec["citations"]).lower()
    assert "29881" in texts or "meniscectomy" in texts
