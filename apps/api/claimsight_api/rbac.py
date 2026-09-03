"""Demo RBAC + light ABAC. Not OIDC — header `X-Actor` maps to a reviewer tier."""

from __future__ import annotations

from typing import Any

TIERS: dict[str, dict[str, Any]] = {
    "adjuster.front": {
        "label": "front-line reviewer",
        "tier": 1,
        "hydrate": False,
        "purge": False,
        "override": False,
        "review_pending": False,
        "specialties": {"endocrinology", "internal"},
    },
    "reviewer.senior": {
        "label": "senior clinical reviewer",
        "tier": 2,
        "hydrate": False,
        "purge": False,
        "override": True,
        "review_pending": True,
        "specialties": {"*"},
    },
    "director.medical": {
        "label": "medical director",
        "tier": 3,
        "hydrate": True,
        "purge": True,
        "override": True,
        "review_pending": True,
        "specialties": {"*"},
    },
    "system": {
        "label": "system",
        "tier": 0,
        "hydrate": False,
        "purge": False,
        "override": False,
        "review_pending": False,
        "specialties": set(),
    },
}

CONFIRM = "ready_for_confirmation"
PENDING = "pending_human_review"


def profile(actor: str) -> dict[str, Any]:
    return TIERS.get(actor) or TIERS["adjuster.front"]


def permissions(actor: str, status: str | None = None) -> dict[str, bool]:
    p = profile(actor)
    awaiting = status in {CONFIRM, PENDING}
    can_confirm = awaiting and (status == CONFIRM or p["review_pending"])
    return {
        "decide": can_confirm,
        "approve": can_confirm,
        "override": can_confirm and bool(p["override"]),
        "escalate": awaiting,
        "hydrate": bool(p["hydrate"]),
        "purge": bool(p["purge"]),
        "review_pending": bool(p["review_pending"]),
    }


def decide_forbidden(actor: str, action: str, status: str) -> str | None:
    p = profile(actor)
    if status not in {CONFIRM, PENDING}:
        return f"claim not awaiting review ({status})"
    if status == PENDING and not p["review_pending"] and action != "escalate":
        return "front-line reviewers may only escalate specialist-queue claims"
    if action == "override_deny" and not p["override"]:
        return "override deny requires senior clinical or medical director"
    if action == "escalate":
        return None
    if status == PENDING and not p["review_pending"]:
        return "pending human review is a senior+ queue"
    return None


def hydrate_forbidden(actor: str) -> str | None:
    if not profile(actor)["hydrate"]:
        return "re-identification is restricted to medical director"
    return None


def purge_forbidden(actor: str) -> str | None:
    if not profile(actor)["purge"]:
        return "purge requires medical director"
    return None
