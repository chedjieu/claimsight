"""LangGraph supervisor: intake → coding → retrieval → parallel specialists → supervisor → compliance."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
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
from claimsight_schemas.models import AgentFinding


class GraphState(TypedDict):
    payload: dict[str, Any]
    specialist_dumps: Annotated[list[dict[str, Any]], operator.add]


def _load(gs: GraphState) -> ClaimState:
    return ClaimState.model_validate(gs["payload"])


def _dump(state: ClaimState) -> dict[str, Any]:
    return {"payload": state.model_dump()}


def _run_specialist(gs: GraphState, fn, agent: str) -> dict[str, Any]:
    st = _load(gs)
    st.findings = []
    before = st.token_used
    st = fn(st)
    return {
        "specialist_dumps": [
            {
                "agent": agent,
                "findings": [f.model_dump() for f in st.findings],
                "traces": {k: v for k, v in st.traces.items() if k == agent},
                "tools_used": {agent: st.tools_used.get(agent, [])},
                "token_delta": st.token_used - before,
                "cost_capped": st.cost_capped,
            }
        ]
    }


def build_graph(retriever: HybridRetriever):
    def intake(gs: GraphState) -> dict[str, Any]:
        return _dump(intake_node(_load(gs)))

    def coding(gs: GraphState) -> dict[str, Any]:
        return _dump(coding_node(_load(gs), retriever))

    def retrieval(gs: GraphState) -> dict[str, Any]:
        return _dump(retrieval_node(_load(gs), retriever))

    def policy(gs: GraphState) -> dict[str, Any]:
        return _run_specialist(gs, policy_node, "policy")

    def necessity(gs: GraphState) -> dict[str, Any]:
        return _run_specialist(gs, necessity_node, "necessity")

    def fraud(gs: GraphState) -> dict[str, Any]:
        return _run_specialist(gs, fraud_node, "fraud")

    def gather(gs: GraphState) -> dict[str, Any]:
        st = _load(gs)
        order = {"policy": 0, "necessity": 1, "fraud": 2}
        dumps = sorted(gs.get("specialist_dumps") or [], key=lambda d: order.get(d.get("agent"), 9))
        for dump in dumps:
            for f in dump.get("findings") or []:
                st.findings.append(AgentFinding.model_validate(f))
            st.traces.update(dump.get("traces") or {})
            for k, v in (dump.get("tools_used") or {}).items():
                st.tools_used[k] = v
            st.token_used += int(dump.get("token_delta") or 0)
            if dump.get("cost_capped"):
                st.cost_capped = True
        return _dump(st)

    def supervisor(gs: GraphState) -> dict[str, Any]:
        return _dump(supervisor_node(_load(gs)))

    def compliance(gs: GraphState) -> dict[str, Any]:
        return _dump(compliance_node(_load(gs)))

    g = StateGraph(GraphState)
    g.add_node("intake", intake)
    g.add_node("coding", coding)
    g.add_node("retrieval", retrieval)
    g.add_node("policy", policy)
    g.add_node("necessity", necessity)
    g.add_node("fraud", fraud)
    g.add_node("gather", gather)
    g.add_node("supervisor", supervisor)
    g.add_node("compliance", compliance)
    g.add_edge(START, "intake")
    g.add_edge("intake", "coding")
    g.add_edge("coding", "retrieval")
    g.add_edge("retrieval", "policy")
    g.add_edge("retrieval", "necessity")
    g.add_edge("retrieval", "fraud")
    g.add_edge("policy", "gather")
    g.add_edge("necessity", "gather")
    g.add_edge("fraud", "gather")
    g.add_edge("gather", "supervisor")
    g.add_edge("supervisor", "compliance")
    g.add_edge("compliance", END)
    return g.compile(checkpointer=MemorySaver())


def run_claim(claim: dict[str, Any], retriever: HybridRetriever, token_budget: int = 8000) -> ClaimState:
    state = ClaimState(
        claim=claim,
        model_name=model_name(),
        prompt_version=PROMPT_VERSION,
        token_budget=token_budget,
    )
    graph = build_graph(retriever)
    maybe_trace("claimsight.run", {"claim_id": claim.get("id")})
    result = graph.invoke(
        {"payload": state.model_dump(), "specialist_dumps": []},
        config={"configurable": {"thread_id": str(claim.get("id") or "anon")}},
    )
    return ClaimState.model_validate(result["payload"])
