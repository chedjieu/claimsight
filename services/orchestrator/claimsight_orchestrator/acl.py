"""Least-privilege tool ACL per specialist."""

from __future__ import annotations

ALLOWED_TOOLS: dict[str, set[str]] = {
    "intake": {"redact", "write_docs"},
    "coding": {"write_graph"},
    "retrieval": {"graph_traverse", "vector_search"},
    "policy": {"graph_traverse", "vector_search"},
    "necessity": {"graph_traverse_history", "vector_search_guidelines"},
    "fraud": {"graph_traverse", "provider_stats"},
    "compliance": {"scan_leak", "scan_injection", "assert_citations"},
    "supervisor": {"synthesize", "score", "route"},
}


def assert_tool_allowed(agent: str, tool: str) -> None:
    allowed = ALLOWED_TOOLS.get(agent, set())
    if tool not in allowed:
        raise PermissionError(f"agent {agent} is not allowed to call {tool}")
