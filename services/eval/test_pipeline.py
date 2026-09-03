from __future__ import annotations

from claimsight_graphrag.data import DEMO_CLAIMS
from claimsight_graphrag.retriever import HybridRetriever
from claimsight_graphrag.store import MemoryGraphStore
from claimsight_orchestrator.graph import run_claim
from claimsight_orchestrator.nodes import fraud_node, necessity_node, policy_node
from claimsight_orchestrator.state import ClaimState


def test_step_therapy_approves_with_graph_history():
    store = MemoryGraphStore()
    state = run_claim(DEMO_CLAIMS["step_therapy"], HybridRetriever(store))
    policy = next(f for f in state.findings if f.agent == "policy")
    nec = next(f for f in state.findings if f.agent == "necessity")
    assert policy.verdict == "approve"
    assert "step_therapy_satisfied" in policy.flags
    assert nec.verdict == "approve"
    assert state.recommendation == "approve"


def test_knee_high_confidence_confirm_path():
    store = MemoryGraphStore()
    state = run_claim(DEMO_CLAIMS["knee"], HybridRetriever(store))
    assert state.recommendation == "approve"
    assert state.route in {"ready_for_confirmation", "pending_human_review"}
    # no fraud flags on a clean ortho claim
    fraud = next(f for f in state.findings if f.agent == "fraud")
    assert fraud.verdict == "approve"


def test_fraud_routes_to_human():
    store = MemoryGraphStore()
    state = run_claim(DEMO_CLAIMS["fraud"], HybridRetriever(store))
    assert state.route == "pending_human_review"
    assert state.recommendation in {"deny", "escalate"}


def test_specialists_are_independently_callable():
    st = ClaimState(
        claim=DEMO_CLAIMS["knee"],
        subgraph={
            "policies": [{"id": "POL-COVER-KNEE", "text": "covered"}],
            "guidelines": [{"id": "GL-AAOS-KNEE"}],
            "failed_steps": [{"id": "CLM-PRIOR-PT", "cpt": ["97110"], "outcome": "failed_conservative"}],
            "provider_stats": {"outlier_score": 0, "watchlist": False, "claim_count": 1},
        },
    )
    st = policy_node(st)
    st = necessity_node(st)
    st = fraud_node(st)
    assert {f.agent for f in st.findings} == {"policy", "necessity", "fraud"}


def test_graph_fans_out_parallel_specialists():
    from claimsight_orchestrator.graph import build_graph

    g = build_graph(HybridRetriever(MemoryGraphStore()))
    names = set(g.get_graph().nodes)
    assert {"policy", "necessity", "fraud", "gather"} <= names
