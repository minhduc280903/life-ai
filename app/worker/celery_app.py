"""Celery application configuration."""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "life_ai",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.worker.tasks"],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Retry configuration
    task_default_retry_delay=30,
    task_max_retries=3,
)
