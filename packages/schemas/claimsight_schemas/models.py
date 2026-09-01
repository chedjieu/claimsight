"""Shared Pydantic contracts for ClaimSight — API, workers, and agents import these."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ClaimStatus = Literal[
    "queued",
    "processing",
    "ready_for_confirmation",
    "pending_human_review",
    "approved",
    "overridden",
    "denied",
    "escalated",
]

Recommendation = Literal["approve", "deny", "escalate"]
FindingVerdict = Literal["approve", "deny", "flag", "insufficient"]


class Citation(BaseModel):
    id: str
    kind: str
    source: str
    text: str
    entity_id: str | None = None


class AgentFinding(BaseModel):
    agent: str
    verdict: FindingVerdict
    confidence: float = 0.0
    narrative: str = ""
    citation_ids: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)


class DocumentIn(BaseModel):
    filename: str = "note.txt"
    text: str


class ClaimCreate(BaseModel):
    id: str | None = None
    patient_id: str
    provider_id: str
    icd10: list[str] = Field(default_factory=list)
    cpt: list[str] = Field(default_factory=list)
    amount_usd: float = 0.0
    service_date: str = ""
    notes: str = ""
    documents: list[DocumentIn] = Field(default_factory=list)
    sensitive_category: str | None = None
    run_immediately: bool = True


class ClaimRecord(BaseModel):
    id: str
    patient_id: str
    provider_id: str
    icd10: list[str]
    cpt: list[str]
    amount_usd: float
    service_date: str
    notes: str = ""
    status: ClaimStatus = "queued"
    recommendation: Recommendation | None = None
    confidence: float = 0.0
    route: str | None = None


class ReviewDecision(BaseModel):
    action: Literal["approve", "edit_approve", "override_deny", "escalate"]
    reason: str | None = None
    edited_recommendation: Recommendation | None = None
    edited_narrative: str | None = None


class RecommendationPacket(BaseModel):
    claim_id: str
    recommendation: Recommendation
    confidence: float
    route: str
    rationale: str
    findings: list[AgentFinding] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    subgraph: dict[str, Any] = Field(default_factory=dict)
    redacted_passages: list[str] = Field(default_factory=list)
    compliance: dict[str, Any] = Field(default_factory=dict)
    token_used: int = 0
    token_budget: int = 8000
    model_name: str = "deterministic-graph-reasoner"
    prompt_version: str = "2026-08-31.1"
    traces: dict[str, str] = Field(default_factory=dict)
