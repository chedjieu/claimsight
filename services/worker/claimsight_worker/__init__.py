"""Celery worker entry — long OCR/embed/orchestrator runs."""

from claimsight_api.celery_app import celery_app, process_claim

__all__ = ["celery_app", "process_claim"]
