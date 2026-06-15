from __future__ import annotations

from datetime import datetime, timezone

import redis

from app.core.config import settings
from app.worker import celery_app

HEARTBEAT_KEY_PREFIX = "marshallbot:runtime_heartbeat:"
HEARTBEAT_TTL_SECONDS = 300


def _redis_client() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def record_runtime_heartbeat(role: str = "beat") -> dict[str, object]:
    timestamp = datetime.now(timezone.utc).isoformat()
    key = f"{HEARTBEAT_KEY_PREFIX}{role}"
    try:
        client = _redis_client()
        client.set(key, timestamp, ex=HEARTBEAT_TTL_SECONDS)
        return {"role": role, "timestamp": timestamp, "ttl_seconds": HEARTBEAT_TTL_SECONDS, "stored": True}
    except Exception as exc:  # pragma: no cover - best-effort runtime telemetry
        return {
            "role": role,
            "timestamp": timestamp,
            "ttl_seconds": HEARTBEAT_TTL_SECONDS,
            "stored": False,
            "error": str(exc),
        }


def _parse_iso_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def get_runtime_health() -> dict[str, object]:
    now = datetime.now(timezone.utc)
    beat_timestamp = None
    worker_timestamp = None
    ping: dict[str, object] = {}
    stats: dict[str, object] = {}
    active: dict[str, list[dict]] = {}
    scheduled: dict[str, list[dict]] = {}
    reserved: dict[str, list[dict]] = {}
    error: str | None = None

    try:
        client = _redis_client()
        beat_timestamp = client.get(f"{HEARTBEAT_KEY_PREFIX}beat")
        worker_timestamp = client.get(f"{HEARTBEAT_KEY_PREFIX}worker")
        inspect = celery_app.control.inspect(timeout=2.0)
        ping = inspect.ping() or {}
        stats = inspect.stats() or {}
        active = inspect.active() or {}
        scheduled = inspect.scheduled() or {}
        reserved = inspect.reserved() or {}
    except Exception as exc:  # pragma: no cover - defensive runtime health fallback
        error = str(exc)

    beat_dt = _parse_iso_timestamp(beat_timestamp)
    worker_dt = _parse_iso_timestamp(worker_timestamp)
    worker_names = sorted(set(ping) | set(stats) | set(active) | set(scheduled) | set(reserved))
    return {
        "redis_url": settings.redis_url.rsplit("@", 1)[-1] if settings.redis_url else "",
        "beat": {
            "timestamp": beat_timestamp,
            "age_seconds": int((now - beat_dt).total_seconds()) if beat_dt else None,
            "healthy": bool(beat_dt and (now - beat_dt).total_seconds() <= HEARTBEAT_TTL_SECONDS),
        },
        "worker": {
            "timestamp": worker_timestamp,
            "age_seconds": int((now - worker_dt).total_seconds()) if worker_dt else None,
            "healthy": bool(worker_dt and (now - worker_dt).total_seconds() <= HEARTBEAT_TTL_SECONDS),
        },
        "worker_count": len(worker_names),
        "workers": [
            {
                "name": worker_name,
                "online": worker_name in ping,
                "active": len(active.get(worker_name, [])),
                "reserved": len(reserved.get(worker_name, [])),
                "scheduled": len(scheduled.get(worker_name, [])),
                "stats": stats.get(worker_name, {}),
            }
            for worker_name in worker_names
        ],
        "error": error,
    }
