# services/orchestrator — LangGraph

Supervisor graph: intake → coding → retrieval → **parallel** policy / necessity / fraud → gather → supervisor → compliance.

## Layout

- `graph.py` — compiled StateGraph with `MemorySaver`
- `nodes.py` — independently testable specialists
- `acl.py` — least-privilege tools (`necessity` cannot `write_graph`)
- `qa.py` — deterministic 5% QA sampling of high-confidence claims
- `llm.py` — Anthropic or deterministic fallback
- `state.py` — `ClaimState`

## Run

Imported by the API. Unit: `pytest services/eval/test_pipeline.py`.

## What this is not

Not a LangGraph `interrupt()` waiter. HITL is persisted claim status.
