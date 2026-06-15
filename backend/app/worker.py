from celery import Celery
from celery.schedules import crontab

from app.core.config import settings
from app.core.logging import configure_logging

configure_logging()
celery_app = Celery(
    "marshallbot",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    timezone="UTC",
    beat_schedule={
        "run-discovery-cycle-every-2-minutes": {
            "task": "marshallbot.run_discovery_cycle",
            "schedule": 120.0,
        },
        "retry-due-alerts-every-5-minutes": {
            "task": "marshallbot.retry_due_alerts",
            "schedule": 300.0,
        },
        "update-runtime-heartbeat-every-minute": {
            "task": "marshallbot.update_runtime_heartbeat",
            "schedule": 60.0,
            "kwargs": {"role": "beat"},
        },
        "run-daily-digest": {
            "task": "marshallbot.run_daily_digest",
            "schedule": crontab(minute=30, hour=23),
        },
    },
)
