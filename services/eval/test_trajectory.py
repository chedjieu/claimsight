from __future__ import annotations

import pytest

from claimsight_orchestrator.acl import ALLOWED_TOOLS, assert_tool_allowed
from claimsight_orchestrator.nodes import necessity_node
from claimsight_orchestrator.state import ClaimState


def test_necessity_cannot_write_graph():
    assert "write_graph" not in ALLOWED_TOOLS["necessity"]
    with pytest.raises(PermissionError):
        assert_tool_allowed("necessity", "write_graph")


def test_necessity_tools_are_read_only():
    state = ClaimState(
        claim={"id": "x", "patient_id": "PAT-1001", "provider_id": "PRV-CHEN", "cpt": ["J3490"], "icd10": ["E11.9"]},
        subgraph={"failed_steps": [{"id": "CLM-PRIOR-MET", "cpt": ["METF"], "outcome": "failed_therapy"}], "guidelines": [{"id": "GL-ADA-GLP1"}]},
    )
    out = necessity_node(state)
    nec = next(f for f in out.findings if f.agent == "necessity")
    assert "write_graph" not in nec.tools_used
    assert "graph_traverse_history" in nec.tools_used


def test_policy_and_fraud_acl():
    assert_tool_allowed("policy", "graph_traverse")
    assert_tool_allowed("fraud", "provider_stats")
    with pytest.raises(PermissionError):
        assert_tool_allowed("fraud", "write_graph")
