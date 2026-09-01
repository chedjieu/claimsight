"""LangGraph supervisor: intake → coding → retrieval → specialists → supervisor → compliance."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from claimsight_graphrag.retriever import HybridRetriever
from claimsight_orchestrator.llm import PROMPT_VERSION, maybe_trace, model_name
from claimsight_orchestrator.nodes import (
    coding_node,
    compliance_node,
    fraud_node,
    intake_node,
    necessity_node,
    policy_node,
    retrieval_node,
    supervisor_node,
)
from claimsight_orchestrator.state import ClaimState


class GraphState(TypedDict):
    payload: dict[str, Any]


def _load(gs: GraphState) -> ClaimState:
    return ClaimState.model_validate(gs["payload"])


def _dump(state: ClaimState) -> GraphState:
    return {"payload": state.model_dump()}


def build_graph(retriever: HybridRetriever):
    def intake(gs: GraphState) -> GraphState:
        return _dump(intake_node(_load(gs)))

    def coding(gs: GraphState) -> GraphState:
        return _dump(coding_node(_load(gs), retriever))

    def retrieval(gs: GraphState) -> GraphState:
        return _dump(retrieval_node(_load(gs), retriever))

    def specialists(gs: GraphState) -> GraphState:
        """Fan-out/fan-in in one node so Pydantic state merges correctly.

        Policy, necessity, and fraud are independently testable functions.
        """
        st = _load(gs)
        st = policy_node(st)
        st = necessity_node(st)
        st = fraud_node(st)
        return _dump(st)

    def supervisor(gs: GraphState) -> GraphState:
        return _dump(supervisor_node(_load(gs)))

    def compliance(gs: GraphState) -> GraphState:
        return _dump(compliance_node(_load(gs)))

    g = StateGraph(GraphState)
    g.add_node("intake", intake)
    g.add_node("coding", coding)
    g.add_node("retrieval", retrieval)
    g.add_node("specialists", specialists)
    g.add_node("supervisor", supervisor)
    g.add_node("compliance", compliance)
    g.add_edge(START, "intake")
    g.add_edge("intake", "coding")
    g.add_edge("coding", "retrieval")
    g.add_edge("retrieval", "specialists")
    g.add_edge("specialists", "supervisor")
    g.add_edge("supervisor", "compliance")
    g.add_edge("compliance", END)
    return g.compile()


def run_claim(claim: dict[str, Any], retriever: HybridRetriever, token_budget: int = 8000) -> ClaimState:
    state = ClaimState(
        claim=claim,
        model_name=model_name(),
        prompt_version=PROMPT_VERSION,
        token_budget=token_budget,
    )
    graph = build_graph(retriever)
    maybe_trace("claimsight.run", {"claim_id": claim.get("id")})
    result = graph.invoke({"payload": state.model_dump()})
    return ClaimState.model_validate(result["payload"])
