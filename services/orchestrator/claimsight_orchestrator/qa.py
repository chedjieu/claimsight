"""Deterministic QA sampling so a slice of high-confidence claims still hit HITL."""

from __future__ import annotations

import hashlib
import os


def sample_rate() -> float:
    try:
        return float(os.getenv("CLAIMSIGHT_QA_SAMPLE_RATE", "0.05"))
    except ValueError:
        return 0.05


def should_qa_sample(claim_id: str, rate: float | None = None) -> bool:
    r = sample_rate() if rate is None else rate
    if r <= 0 or not claim_id:
        return False
    digest = int(hashlib.sha256(claim_id.encode("utf-8")).hexdigest(), 16)
    return (digest % 10_000) / 10_000 < r
