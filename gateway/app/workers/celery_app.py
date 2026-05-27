"""Celery application configuration."""

from __future__ import annotations

from celery import Celery

from app.config import settings

celery_app = Celery(
    "sentinel",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.persist_trace", "app.workers.evaluate_trace"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=4,
)

# Auto-discover tasks in the workers module
celery_app.autodiscover_tasks(["app.workers"])
