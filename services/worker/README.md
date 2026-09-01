# services/worker — Celery

Long-running orchestrator jobs. Demo path does **not** require this process.

## Run

```bash
celery -A claimsight_api.celery_app.celery_app worker --loglevel=INFO
```

Task: `claimsight.process_claim(claim_id)`.

Needs Redis (`CELERY_BROKER_URL`). Compose starts this service automatically.

## What this is not

Not OCR yet (text documents only). Embeddings are token-overlap, not a GPU job.
