from celery import Celery

from ..config import settings

celery = Celery(
    "dump_analyzer",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.heap_task", "app.tasks.thread_task"],
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)
