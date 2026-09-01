"""LangGraph-facing claim state."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from claimsight_schemas.models import AgentFinding, Citation


class ClaimState(BaseModel):
    claim: dict[str, Any]
    redacted_notes: str = ""
    redacted_docs: list[str] = Field(default_factory=list)
    phi_mapping: dict[str, str] = Field(default_factory=dict)
    phi_findings: list[str] = Field(default_factory=list)
    injection_hits: list[str] = Field(default_factory=list)
    subgraph: dict[str, Any] = Field(default_factory=dict)
    citations: list[Citation] = Field(default_factory=list)
    findings: list[AgentFinding] = Field(default_factory=list)
    traces: dict[str, str] = Field(default_factory=dict)
    tools_used: dict[str, list[str]] = Field(default_factory=dict)
    recommendation: str = "escalate"
    confidence: float = 0.0
    route: str = "pending_human_review"
    rationale: str = ""
    compliance: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    token_used: int = 0
    token_budget: int = 8000
    model_name: str = "deterministic-graph-reasoner"
    prompt_version: str = "2026-08-31.1"
    cost_capped: bool = False
