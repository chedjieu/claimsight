# ClaimSight — as built

Living record of what actually shipped versus [PLAN.md](PLAN.md). Dated 2026-08-31. PLAN is not rewritten to hide deviations.

## Phase status

| Phase | Status | How to exercise |
|---|---|---|
| 0 Foundations | done | `pytest services/eval/test_api.py::test_health`; `uvicorn claimsight_api.main:app` |
| 1 Vector RAG | done | `pytest services/eval/test_retrieval.py` |
| 2 GraphRAG | done | `pytest services/eval/test_retrieval.py::test_vector_only_misses_prior_metformin_failure` |
| 3 Supervisor | done | `pytest services/eval/test_pipeline.py` |
| 4 HITL | done | UI Approve / Edit / Override / Escalate; `POST /claims/{id}/decide` |
| 5 Security | done | `pytest services/eval/test_security.py` |
| 6 Eval | done | `pytest -q`; CI `.github/workflows/ci.yml` |
| 7 Multi-cloud | done (stubs) | `infra/terraform/{gcp,aws}/main.tf`; `/metrics`; `CLAIMSIGHT_TOKEN_BUDGET` |

## Module map

| Concern | Path |
|---|---|
| Shared contracts | `packages/schemas/claimsight_schemas/` |
| Prompts | `packages/prompts/claimsight_prompts/` |
| Object storage | `packages/storage/claimsight_storage/` |
| PHI guard | `services/phi_guard/claimsight_phi_guard/` |
| GraphRAG | `services/graphrag/claimsight_graphrag/` (`data.py`, `store.py`, `retriever.py`) |
| Orchestrator | `services/orchestrator/claimsight_orchestrator/` (`graph.py`, `nodes.py`, `acl.py`) |
| API / HITL | `apps/api/claimsight_api/` (`main.py`, `pipeline.py`) |
| Worker | `services/worker/claimsight_worker/` + `claimsight_api.celery_app` |
| UI | `apps/web/src/App.tsx` |
| Gold + CI | `services/eval/` + `.github/workflows/ci.yml` |
| Compose / k8s / tf | `infra/` |

## Deviations from PLAN.md

1. **Packages live at workspace root**, not nested under a `claimsight/` directory — the brief was already at the workspace root.
2. **LLM is optional.** `CLAIMSIGHT_LLM_PROVIDER=auto` uses Anthropic when `ANTHROPIC_API_KEY` is set, otherwise a **deterministic graph reasoner**. CI always uses deterministic.
3. **HITL is API + SQLite/Postgres, not LangGraph `interrupt()`.** Claims persist as `pending_human_review` / `ready_for_confirmation`; `POST /claims/{id}/decide` resumes. Survives process restart.
4. **Specialists run inside one LangGraph node** so Pydantic `ClaimState` merges cleanly. Policy, necessity, and fraud remain separately tested functions (same pattern as GXO Sentinel).
5. **App DB defaults to SQLite** so pytest and a no-Docker API run work. Compose still provides Postgres+pgvector.
6. **Vector search is token-Jaccard** over seeded passages, not OpenAI embeddings / pgvector cosine. Same intent as hybrid RAG; no embedding API required for the laptop demo. pgvector image is in Compose for later.
7. **MemoryGraphStore is the CI source of truth.** Neo4j is seeded when Bolt is reachable; subgraph reads still go through the in-memory model so tests do not depend on Aura.
8. **Auth is demo header `X-Actor`** with three reviewer tiers, not OIDC. SSO is documented as the GCP/AWS path.
9. **Celery worker is in Compose;** the API runs the graph in-process on ingest so the demo does not depend on the worker.
10. **Pydantic models (not Pydantic AI SDK)** for typed I/O. Provider swap is still a config change (`CLAIMSIGHT_LLM_PROVIDER`).
11. **RAGAS library not vendored.** Faithfulness is a citation-grounding hit-rate in `test_ragas.py`. LLM-as-judge lives in `test_llm_judge.py` and skips without a key.
12. **No `packages/queue` package.** Queue is env-driven Celery/Redis (`CELERY_BROKER_URL`).
13. **Tailwind/shadcn not used.** Distinctive clinical CSS in `apps/web/src/styles.css` (Fraunces / Source Serif / IBM Plex).
14. **WebSocket `/ws/queue` exists** but the console polls REST; WS is a stub for later push.

## Mocked vs real

| Surface | Real | Mocked |
|---|---|---|
| Multi-agent graph, HITL, audit, PHI redaction | yes | — |
| Knowledge (patients, policies, guidelines) | yes (synthetic) | not a real payer |
| Clinical notes / faxes | — | seeded strings with PHI-shaped fields |
| OCR | — | text documents only |
| LLM completions | optional Anthropic | deterministic fallback |
| MinIO / S3 | adapter | disk fallback if boto unconfigured |
| SSO / KMS / Cloud Run / ECS | stubs | Terraform + k8s adapters |

## Known gaps

- No column-level encryption at rest (PHI map is JSON on the claim row; documents are plaintext on disk/MinIO in dev).
- No Playwright E2E in CI (pytest covers the decision path).
- Neo4j Cypher writes on seed; reads for retrieval use MemoryGraphStore.
- Cost cap is token-estimate (chars/4), not provider billing APIs.
- Terraform is not applied; no live GCP/AWS cluster.

## Leadership demo path

See [DEMO.md](DEMO.md).
