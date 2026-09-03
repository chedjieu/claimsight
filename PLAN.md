# ClaimSight — Implementation Plan

Canonical in-repo copy of the implementation plan (intent). Frozen except dated addenda. What actually shipped is recorded in [docs/AS_BUILT.md](docs/AS_BUILT.md). The original brief remains at [ClaimSight-Capstone-Design.md](ClaimSight-Capstone-Design.md). Architecture diagrams: [high-level](docs/architecture/claimsight-high-level-architecture.mermaid), [orchestration](docs/architecture/claimsight-agent-orchestration.mermaid).

**Official name: ClaimSight.** Tagline: *AI drafts, humans decide.*

Greenfield repo. This plan turns the brief into a runnable vertical slice: **claim in → PHI redaction → GraphRAG → specialist agents → HITL recommendation → labeled feedback**, with eval, cost caps, and adapters for GCP/AWS later.

## Target shape

**Now:** Docker Compose on a laptop (or SQLite + in-memory graph with no Docker). Synthetic PHI-shaped claims. Real LangGraph + FastAPI + React reviewer console.

**Later:** Same services, swap adapters — Postgres → Cloud SQL / RDS, Neo4j → Aura, MinIO → GCS / S3, compose → Cloud Run / ECS. No rewrite of agents or graph schema.

Three document types stay separate: brief (why), this plan (how we intended), as-built (what exists). Root README is the front door. Every package has a README.

## Cloud strategy

| Concern | Local | GCP later | AWS later |
|---|---|---|---|
| API / workers | Compose | Cloud Run | ECS Fargate |
| Postgres + pgvector | `pgvector/pgvector` | Cloud SQL | RDS |
| Redis | container | Memorystore | ElastiCache |
| Neo4j | Community container | Aura / GCE | Aura / EC2 |
| Object storage | MinIO (S3 API) | GCS | S3 |
| Secrets | `.env` | Secret Manager | Secrets Manager |

## Phases

| Phase | Scope | Exit |
|---|---|---|
| 0 Foundations | Compose, FastAPI, React shell, docs | `pytest` health + README quickstart |
| 1 Vector RAG | Token/vector search over guidelines | gold retrieval tests |
| 2 GraphRAG | Neo4j/memory schema + hybrid retrieve | vector-only miss fixture |
| 3 Supervisor | LangGraph + Policy/Necessity/Fraud | typed findings + confidence |
| 4 HITL | Review queue, console, feedback | leadership demo |
| 5 Security | PHI guard, audit, demo RBAC | red-team tests |
| 6 Eval | RAGAS-style, trajectory, LLM-judge, CI | `pytest -q` on every PR |
| 7 Multi-cloud | Terraform stubs, cost cap, ops metrics | adapters documented |

## Non-goals (v1)

- Real PHI or live payer data
- Fine-tuning / RFT
- Production HIPAA BAAs (checklist only)
- Binding to Supabase / Vercel

## Addendum — 2026-09-01

Closed remaining v1 plan items that the first as-built left open: Fernet vault + sealed object store, Neo4j Cypher history reads + `Decision` nodes, parallel specialist graph, 5% QA sampling, demo RBAC, SSE live queue, subgraph visualization, right-to-delete purge, drift slices on `/metrics`, Playwright desk e2e, and [docs/COMPLIANCE.md](docs/COMPLIANCE.md). Cloud apply, KMS, and hosted embeddings stay later.
