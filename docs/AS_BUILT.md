# ClaimSight — as built

Living record of what actually shipped versus [PLAN.md](../PLAN.md). Dated 2026-09-01. PLAN is not rewritten to hide deviations.

## Phase status

| Phase | Status | How to exercise |
|---|---|---|
| 0 Foundations | done | `pytest services/eval/test_api.py::test_health`; `uvicorn claimsight_api.main:app` |
| 1 Vector RAG | done | `pytest services/eval/test_retrieval.py` |
| 2 GraphRAG | done | `pytest services/eval/test_retrieval.py::test_vector_only_misses_prior_metformin_failure` |
| 3 Supervisor | done | `pytest services/eval/test_pipeline.py` — policy / necessity / fraud are parallel LangGraph nodes |
| 4 HITL | done | UI Approve / Edit / Override / Escalate; `POST /claims/{id}/decide`; SSE `/events` |
| 5 Security | done | `pytest services/eval/test_security.py`; vault + RBAC + purge in `test_ops.py`; [COMPLIANCE.md](COMPLIANCE.md) |
| 6 Eval | done | `pytest -q`; Playwright desk e2e; CI `.github/workflows/ci.yml` |
| 7 Multi-cloud | done (stubs) | `infra/terraform/{gcp,aws}/main.tf`; `/metrics` drift slices; `CLAIMSIGHT_TOKEN_BUDGET` |

## Module map

| Concern | Path |
|---|---|
| Shared contracts | `packages/schemas/claimsight_schemas/` |
| Prompts | `packages/prompts/claimsight_prompts/` |
| Object storage | `packages/storage/claimsight_storage/` (Fernet-sealed bodies) |
| PHI guard + vault | `services/phi_guard/claimsight_phi_guard/` (`phi.py`, `vault.py`) |
| GraphRAG | `services/graphrag/claimsight_graphrag/` (`data.py`, `store.py`, `retriever.py`) |
| Orchestrator | `services/orchestrator/claimsight_orchestrator/` (`graph.py`, `nodes.py`, `acl.py`, `qa.py`) |
| API / HITL | `apps/api/claimsight_api/` (`main.py`, `pipeline.py`, `rbac.py`, `events.py`) |
| Worker | `services/worker/claimsight_worker/` + `claimsight_api.celery_app` |
| UI | `apps/web/src/App.tsx`, `GraphMap.tsx` |
| Gold + CI | `services/eval/` + `.github/workflows/ci.yml` |
| Compose / k8s / tf | `infra/` |

## Deviations from PLAN.md

1. **Packages live at workspace root**, not nested under a `claimsight/` directory — the brief was already at the workspace root.
2. **LLM is optional.** `CLAIMSIGHT_LLM_PROVIDER=auto` uses Anthropic when `ANTHROPIC_API_KEY` is set, otherwise a **deterministic graph reasoner**. CI always uses deterministic.
3. **HITL is API + SQLite/Postgres, not LangGraph `interrupt()`.** Claims persist as `pending_human_review` / `ready_for_confirmation`; `POST /claims/{id}/decide` resumes. Survives process restart. The graph still compiles with a `MemorySaver` checkpointer.
4. **Specialists are parallel LangGraph nodes** (`policy`, `necessity`, `fraud` → `gather`). They remain independently testable functions.
5. **App DB defaults to SQLite** so pytest and a no-Docker API run work. Compose still provides Postgres+pgvector.
6. **Vector search is token-Jaccard** over seeded passages, not OpenAI embeddings / pgvector cosine. Same intent as hybrid RAG; no embedding API required for the laptop demo. pgvector image is in Compose for later.
7. **MemoryGraphStore is the CI source of truth.** Neo4j is seeded when Bolt is reachable; **history and provider stats are read via Cypher** with memory fallback.
8. **Auth is demo header `X-Actor`** with three reviewer tiers and enforced RBAC (hydrate/purge director-only; override senior+). SSO is documented as the GCP/AWS path.
9. **Celery worker is in Compose.** Demo endpoints still run the graph in-process so the walkthrough does not depend on the worker. `CLAIMSIGHT_ASYNC=true` enqueues `process_claim`.
10. **Pydantic models (not Pydantic AI SDK)** for typed I/O. Provider swap is still a config change (`CLAIMSIGHT_LLM_PROVIDER`).
11. **RAGAS library not vendored.** Faithfulness is a citation-grounding hit-rate in `test_ragas.py`. LLM-as-judge lives in `test_llm_judge.py` and skips without a key.
12. **No `packages/queue` package.** Queue is env-driven Celery/Redis (`CELERY_BROKER_URL`).
13. **Tailwind/shadcn not used.** Distinctive clinical CSS in `apps/web/src/styles.css` (Fraunces / Source Serif / IBM Plex).
14. **Console uses SSE `/events`** for live queue refresh; `/ws/queue` publishes the same bus.

## Mocked vs real

| Surface | Real | Mocked |
|---|---|---|
| Multi-agent graph, HITL, audit, PHI redaction, vault encryption | yes | — |
| Knowledge (patients, policies, guidelines) | yes (synthetic) | not a real payer |
| Clinical notes / faxes | — | seeded strings with PHI-shaped fields |
| OCR | — | text documents only |
| LLM completions | optional Anthropic | deterministic fallback |
| MinIO / S3 | adapter + sealed bodies | disk fallback if boto unconfigured |
| SSO / KMS / Cloud Run / ECS | stubs | Terraform + k8s adapters |

## Known gaps

- Vault key is env-derived Fernet, not cloud KMS.
- Cost cap is token-estimate (chars/4), not provider billing APIs.
- Terraform is not applied; no live GCP/AWS cluster.
- Vector search is still Jaccard, not hosted embeddings.

## Leadership demo path

See [DEMO.md](DEMO.md).
