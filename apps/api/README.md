# apps/api — FastAPI

Auth'd (demo `X-Actor`) entry point. Enqueues/runs claims, serves the review queue, audit, and metrics.

## Layout

- `claimsight_api/main.py` — routes
- `claimsight_api/pipeline.py` — ingest, orchestrate, decide
- `claimsight_api/models.py` — SQLAlchemy claims / audit / eval labels
- `claimsight_api/celery_app.py` — optional worker tasks

## Run

```bash
pip install -e ".[dev]"
uvicorn claimsight_api.main:app --reload
```

OpenAPI: http://localhost:8000/docs

Env: see `.env.example` (`DATABASE_URL`, `CLAIMSIGHT_LLM_PROVIDER`, `CLAIMSIGHT_TOKEN_BUDGET`).

## What this is not

Not OIDC. Not a blocking inference server in production (Compose worker exists; demo runs in-process).
