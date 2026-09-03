# ClaimSight

**AI drafts, humans decide.**

ClaimSight is a multi-agent GenAI platform for health-insurance claims review. It redacts PHI before any model call, reasons over a knowledge graph plus guideline search, and produces a cited recommendation. Humans confirm or override — never an unsupervised clinical judgment.

Brief (why): [ClaimSight-Capstone-Design.md](ClaimSight-Capstone-Design.md) · Plan (intent): [PLAN.md](PLAN.md) · As-built (reality): [docs/AS_BUILT.md](docs/AS_BUILT.md) · Demo script: [docs/DEMO.md](docs/DEMO.md)

Architecture: [high-level](docs/architecture/claimsight-high-level-architecture.mermaid) · [orchestration](docs/architecture/claimsight-agent-orchestration.mermaid)

## Prerequisites

- Python 3.12+, Node 20+ (for the console)
- Optional: Docker Desktop (Compose stack: Postgres+pgvector, Neo4j, Redis, MinIO)
- Optional: `ANTHROPIC_API_KEY` (otherwise a deterministic graph reasoner)

## Quickstart (no Docker)

```bash
cp env.example .env
pip install -e ".[dev]"
pytest -q
uvicorn claimsight_api.main:app --reload
```

In another terminal:

```bash
cd apps/web
npm install
npm run dev
```

Open http://localhost:5173 — **Step-therapy demo** submits a synthetic claim through the full agent graph.

API docs: http://localhost:8000/docs

## Quickstart (Compose)

```bash
cp env.example .env
docker compose up --build
```

Console: http://localhost:5173 · API: http://localhost:8000 · Neo4j: http://localhost:7474 · MinIO: http://localhost:9001

## Phase status

| Phase | Status |
|---|---|
| 0 Foundations | done |
| 1 Vector RAG | done |
| 2 GraphRAG | done |
| 3 Multi-agent + Supervisor | done |
| 4 Human-in-the-loop | done |
| 5 Security | done |
| 6 Evaluation | done |
| 7 Multi-cloud adapters | stubs (Terraform GCP + AWS) |

## Doc index

| Doc | Question it answers |
|---|---|
| [ClaimSight-Capstone-Design.md](ClaimSight-Capstone-Design.md) | Why this product |
| [PLAN.md](PLAN.md) | How we intended to build it |
| [docs/AS_BUILT.md](docs/AS_BUILT.md) | What actually exists |
| [docs/DEMO.md](docs/DEMO.md) | Leadership walkthrough |
| [docs/COMPLIANCE.md](docs/COMPLIANCE.md) | HIPAA-style checklist (not a certification) |
| [apps/web/README.md](apps/web/README.md) | Reviewer console |
| [apps/api/README.md](apps/api/README.md) | FastAPI |
| [services/orchestrator/README.md](services/orchestrator/README.md) | LangGraph agents |
| [services/worker/README.md](services/worker/README.md) | Celery |
| [services/graphrag/README.md](services/graphrag/README.md) | Graph + hybrid retrieve |
| [services/phi_guard/README.md](services/phi_guard/README.md) | Redaction |
| [services/eval/README.md](services/eval/README.md) | Gold sets and CI |
| [packages/schemas/README.md](packages/schemas/README.md) | Shared models |
| [packages/prompts/README.md](packages/prompts/README.md) | Versioned prompts |
| [packages/storage/README.md](packages/storage/README.md) | S3/MinIO adapter |
| [infra/README.md](infra/README.md) | Compose, k8s, Terraform |

## Non-goals

- Real PHI or live payer data
- Fine-tuning
- Production HIPAA certification (documented as a checklist, not claimed)
