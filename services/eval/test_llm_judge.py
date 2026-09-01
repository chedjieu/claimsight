"""LLM-as-judge — skipped without ANTHROPIC_API_KEY (CI uses deterministic)."""

from __future__ import annotations

import os

import pytest

from claimsight_graphrag.data import DEMO_CLAIMS
from claimsight_graphrag.retriever import HybridRetriever
from claimsight_graphrag.store import MemoryGraphStore
from claimsight_orchestrator.graph import run_claim
from claimsight_orchestrator.llm import complete_json, provider_name


@pytest.mark.llm
def test_judge_step_therapy_grounded():
    if provider_name() == "deterministic" and not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("no LLM key")
    state = run_claim(DEMO_CLAIMS["step_therapy"], HybridRetriever(MemoryGraphStore()))
    rubric = {
        "citation_completeness": 0,
        "clinical_soundness": 0,
        "escalation_appropriate": 0,
        "notes": "",
    }
    judged = complete_json(
        "Score 0-1 for citation_completeness, clinical_soundness, escalation_appropriate. JSON only.",
        state.rationale,
        rubric,
    )
    assert isinstance(judged, dict)
