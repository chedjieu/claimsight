from __future__ import annotations

import os

from celery import Celery

from claimsight_api.config import settings

celery_app = Celery(
    "claimsight",
    broker=os.getenv("CELERY_BROKER_URL", settings.celery_broker_url),
    backend=os.getenv("CELERY_RESULT_BACKEND", settings.celery_broker_url),
)
celery_app.conf.update(task_serializer="json", accept_content=["json"], result_serializer="json")


@celery_app.task(name="claimsight.process_claim")
def process_claim(claim_id: str) -> str:
    from claimsight_api.pipeline import run_and_store

    return run_and_store(claim_id, actor="worker")
