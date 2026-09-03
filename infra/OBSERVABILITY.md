# Observability + cost governance (Phase 7)

Local:
- Structured logs from FastAPI + LangGraph traces (`traces` on each packet)
- Optional LangSmith when `LANGSMITH_TRACING=true`
- `/metrics` surfaces override rate, override-by-CPT, confidence histogram, QA samples, mean tokens, queue depth

Cost cap:
- `CLAIMSIGHT_TOKEN_BUDGET` (default 8000) is enforced in the supervisor.
- Exceeding the budget forces `pending_human_review` (`cost_capped=true`).

Drift:
- Override rate by claim type is a first-class ops metric.
- Prompt version is stamped on every packet (`CLAIMSIGHT_PROMPT_VERSION`).

GCP later: Cloud Logging + Error Reporting + Cloud Trace. AWS later: CloudWatch.
Sentry/PostHog are env-optional (`SENTRY_DSN`) and not required for the demo.
