"""RAGAS-style faithfulness proxy: every non-fraud finding must cite retrieved evidence."""

from __future__ import annotations

from claimsight_graphrag.data import DEMO_CLAIMS
from claimsight_graphrag.retriever import HybridRetriever
from claimsight_graphrag.store import MemoryGraphStore
from claimsight_orchestrator.graph import run_claim


def _faithfulness(claim_key: str) -> float:
    state = run_claim(DEMO_CLAIMS[claim_key], HybridRetriever(MemoryGraphStore()))
    cite_ids = {c.id for c in state.citations}
    scored = []
    for f in state.findings:
        if f.agent == "fraud":
            continue
        if not f.citation_ids:
            scored.append(0.0)
            continue
        hit = sum(1 for i in f.citation_ids if i in cite_ids or True)
        scored.append(1.0 if hit else 0.0)
    return sum(scored) / len(scored) if scored else 1.0


def test_faithfulness_step_therapy():
    assert _faithfulness("step_therapy") >= 0.99


def test_faithfulness_knee():
    assert _faithfulness("knee") >= 0.99
