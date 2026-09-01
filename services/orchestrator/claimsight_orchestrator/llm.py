"""LLM factory: Anthropic when keyed, else deterministic grounded fallback."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from claimsight_prompts.templates import PROMPT_VERSION as PACKAGED_PROMPT

log = logging.getLogger(__name__)

PROMPT_VERSION = os.getenv("CLAIMSIGHT_PROMPT_VERSION", PACKAGED_PROMPT)


def provider_name() -> str:
    forced = os.getenv("CLAIMSIGHT_LLM_PROVIDER", "auto").lower()
    if forced == "deterministic":
        return "deterministic"
    if forced == "anthropic" or (forced == "auto" and os.getenv("ANTHROPIC_API_KEY")):
        return "anthropic"
    return "deterministic"


def model_name() -> str:
    if provider_name() == "anthropic":
        return os.getenv("CLAIMSIGHT_MODEL_NAME", "claude-sonnet-4-5")
    return "deterministic-graph-reasoner"


def complete_json(system: str, user: str, fallback: dict[str, Any]) -> dict[str, Any]:
    if provider_name() != "anthropic":
        return fallback
    try:
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = ChatAnthropic(model=model_name(), temperature=0, max_tokens=1600)
        msg = llm.invoke(
            [
                SystemMessage(content=system + "\nReturn ONLY valid JSON. Never invent citations."),
                HumanMessage(content=user),
            ]
        )
        text = getattr(msg, "content", "") or ""
        if isinstance(text, list):
            text = "".join(
                getattr(p, "text", str(p)) if not isinstance(p, str) else p for p in text
            )
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
    except Exception as exc:  # noqa: BLE001
        log.warning("LLM complete_json failed, using grounded fallback: %s", exc)
    return fallback


def maybe_trace(run_name: str, payload: dict[str, Any]) -> None:
    if os.getenv("LANGSMITH_TRACING", "").lower() == "true" and os.getenv("LANGSMITH_API_KEY"):
        try:
            from langsmith import Client

            Client().create_run(name=run_name, inputs=payload, run_type="chain")
        except Exception as exc:  # noqa: BLE001
            log.debug("langsmith emit skipped: %s", exc)


def estimate_tokens(*parts: str) -> int:
    n = sum(len(p or "") for p in parts)
    return max(1, n // 4)
