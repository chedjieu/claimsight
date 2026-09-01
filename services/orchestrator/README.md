# services/orchestrator — LangGraph

Supervisor graph: intake → coding → retrieval → specialists (policy, necessity, fraud) → supervisor → compliance.

## Layout

- `graph.py` — compiled StateGraph
- `nodes.py` — independently testable specialists
- `acl.py` — least-privilege tools (`necessity` cannot `write_graph`)
- `llm.py` — Anthropic or deterministic fallback
- `state.py` — `ClaimState`

## Run

Imported by the API. Unit: `pytest services/eval/test_pipeline.py`.

## What this is not

Not a LangGraph `interrupt()` waiter. HITL is persisted claim status. Specialists are sequential inside one node for Pydantic merge (see as-built).
