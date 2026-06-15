from __future__ import annotations

from datetime import datetime, timezone
from inspect import signature

from app.core.config import settings
from app.core.dedupe import fingerprint
from app.core.scoring import ScoreBreakdown
from app.services.alerting import build_alert_payload
from app.services.alerting import build_alert_message
from app.services.alerting import delivery_ready
from app.services.alerting import within_alert_budget
from app.services.enrichment import enrich_website
from app.services.orchestration import process_source
from app.services.ranking import RankingConfig
from app.services.registry import build_default_registry
from app.core.runtime_config import load_runtime_config
from app.services.runtime_health import record_runtime_heartbeat
from app.core.source_config import SourceConfig
from app.services.telegram import TelegramBotClient
from app.worker import celery_app
from app.db.repository import count_alerts_sent_since, get_alert_attempt, can_retry_alert, list_due_alert_retries, mark_alert_failed, mark_alert_sent, register_alert_attempt, retry_backoff_minutes, store_website_snapshot
from app.db.queries import list_ranking_dashboard


@celery_app.task(name="marshallbot.ingest_candidate", bind=True, autoretry_for=(Exception,), retry_backoff=True)
def ingest_candidate(self, payload: dict) -> dict:
    return {
        "received_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
        "status": "queued_for_enrichment",
    }


@celery_app.task(name="marshallbot.enrich_candidate", bind=True, autoretry_for=(Exception,), retry_backoff=True)
def enrich_candidate(self, payload: dict) -> dict:
    payload["enriched_at"] = datetime.now(timezone.utc).isoformat()
    payload["has_website"] = bool(payload.get("website_url"))
    payload["has_telegram"] = bool(payload.get("telegram_url"))
    return payload


@celery_app.task(name="marshallbot.score_candidate", bind=True, autoretry_for=(Exception,), retry_backoff=True)
def score_candidate(self, payload: dict) -> dict:
    breakdown = ScoreBreakdown(
        freshness=float(payload.get("freshness", 0)),
        telegram_presence=float(payload.get("telegram_presence", 0)),
        social_activity=float(payload.get("social_activity", 0)),
        website_quality=float(payload.get("website_quality", 0)),
        growth_rate=float(payload.get("growth_rate", 0)),
        source_quality=float(payload.get("source_quality", 0)),
        community_activity=float(payload.get("community_activity", 0)),
        spam_penalty=float(payload.get("spam_penalty", 0)),
    )
    payload["score"] = breakdown.final_score()
    payload["scored_at"] = datetime.now(timezone.utc).isoformat()
    return payload


@celery_app.task(name="marshallbot.maybe_alert", bind=True, autoretry_for=(Exception,), retry_backoff=True)
def maybe_alert(self, payload: dict) -> dict:
    record_runtime_heartbeat(role="worker")
    runtime_config = load_runtime_config()
    min_score_to_alert = float(runtime_config["min_score_to_alert"])
    daily_alert_limit = int(runtime_config["daily_alert_limit"])
    alert = build_alert_payload(payload, float(payload.get("score", 0)), min_score_to_alert)
    sent = False
    alert_delivery_ready = delivery_ready(settings.telegram_bot_token, settings.telegram_chat_id)
    alerts_sent_recently = count_alerts_sent_since(hours=24)
    alert_budget_available = within_alert_budget(alerts_sent_recently, daily_alert_limit)
    if alert is not None and alert_delivery_ready:
        if not alert_budget_available:
            return {
                "alert_created": True,
                "alert_sent": False,
                "alert": alert,
                "daily_alert_limit": daily_alert_limit,
                "delivery_ready": alert_delivery_ready,
                "delivery_skipped": "daily_limit_reached",
                "alerts_sent_recently": alerts_sent_recently,
            }
        dedupe_key = fingerprint(
            str(payload.get("canonical_name", "")),
            str(payload.get("website_url", "")),
            str(payload.get("telegram_url", "")),
            str(payload.get("score", "")),
        )
        sent = register_alert_attempt(
            project_id=payload.get("project_id"),
            chat_id=settings.telegram_chat_id,
            score=float(payload.get("score", 0)),
            dedupe_key=dedupe_key,
        )
        if sent:
            message = build_alert_message(payload, float(payload.get("score", 0)))
            # Best-effort notification; task remains idempotent via alerts_sent dedupe_key.
            import asyncio

            try:
                result = asyncio.run(TelegramBotClient().send_message(settings.telegram_chat_id, message))
            except Exception as exc:
                mark_alert_failed(dedupe_key, str(exc))
                raise
            else:
                mark_alert_sent(dedupe_key, str(result.get("result", {}).get("message_id")) if result else None)
    return {
        "alert_created": alert is not None,
        "alert_sent": sent,
        "alert": alert,
        "daily_alert_limit": daily_alert_limit,
        "delivery_ready": alert_delivery_ready,
        "alerts_sent_recently": alerts_sent_recently,
        "alert_budget_available": alert_budget_available,
        "delivery_skipped": None if alert_delivery_ready else "telegram_not_configured",
    }


def _process_source_with_weights(source, ranking: RankingConfig, source_config: SourceConfig, runtime_weights: dict) -> list[dict]:
    process_kwargs = {
        "source_config": source_config,
        "enrich_websites": False,
        "score_cooldown_minutes": 30,
    }
    if "default_signals" in signature(process_source).parameters:
        process_kwargs["default_signals"] = {"weights": runtime_weights}
    return process_source(source, ranking, **process_kwargs)


def retry_alert_delivery(alert_id: int) -> dict:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return {"ok": False, "reason": "telegram_not_configured", "alert_id": alert_id}

    alert = get_alert_attempt(alert_id)
    if not alert:
        return {"ok": False, "reason": "not_found", "alert_id": alert_id}
    if alert.get("delivery_status") == "sent":
        return {"ok": True, "reason": "already_sent", "alert_id": alert_id, "delivery_status": "sent"}
    can_retry, retry_reason = can_retry_alert(alert)
    if not can_retry:
        return {
            "ok": False,
            "alert_id": alert_id,
            "reason": retry_reason,
            "retry_count": int(alert.get("retry_count", 0) or 0),
            "next_retry_at": alert.get("next_retry_at"),
        }

    project_payload = {
        "canonical_name": alert.get("canonical_name"),
        "chain": alert.get("chain"),
        "website_url": alert.get("website_url"),
        "telegram_url": alert.get("telegram_url"),
        "x_url": alert.get("x_url"),
        "discord_url": alert.get("discord_url"),
        "launch_source": alert.get("launch_source"),
        "first_seen_at": alert.get("sent_at"),
        "score_explanations": (alert.get("score_reasons") or {}).get("explanations", []),
    }
    message = build_alert_message(project_payload, float(alert.get("score_at_send", 0) or 0))
    dedupe_key = str(alert.get("dedupe_key"))

    import asyncio

    try:
        result = asyncio.run(TelegramBotClient().send_message(settings.telegram_chat_id, message))
    except Exception as exc:
        mark_alert_failed(dedupe_key, str(exc))
        return {
            "ok": False,
            "alert_id": alert_id,
            "reason": "delivery_failed",
            "error": str(exc),
            "retry_count": int(alert.get("retry_count", 0) or 0) + 1,
            "next_retry_minutes": retry_backoff_minutes(int(alert.get("retry_count", 0) or 0) + 1),
        }

    message_id = str(result.get("result", {}).get("message_id")) if result else None
    mark_alert_sent(dedupe_key, message_id)
    return {
        "ok": True,
        "alert_id": alert_id,
        "delivery_status": "sent",
        "message_id": message_id,
    }


@celery_app.task(name="marshallbot.retry_due_alerts", bind=True, autoretry_for=(Exception,), retry_backoff=True)
def retry_due_alerts(self, limit: int = 50) -> dict:
    record_runtime_heartbeat(role="worker")
    due_alerts = list_due_alert_retries(limit=limit)
    results: list[dict] = []
    for alert in due_alerts:
        results.append(retry_alert_delivery(int(alert["id"])))
    return {
        "limit": limit,
        "due_count": len(due_alerts),
        "retried_count": len([item for item in results if item.get("ok")]),
        "blocked_count": len([item for item in results if not item.get("ok")]),
        "results": results,
    }


@celery_app.task(name="marshallbot.run_discovery_cycle", bind=True, autoretry_for=(Exception,), retry_backoff=True)
def run_discovery_cycle(self) -> dict:
    record_runtime_heartbeat(role="worker")
    source_config = SourceConfig.load()
    runtime_config = load_runtime_config()
    registry = build_default_registry(source_config)
    ranking = RankingConfig(
        min_score_to_alert=float(runtime_config["min_score_to_alert"]),
        daily_alert_limit=int(runtime_config["daily_alert_limit"]),
    )
    summary: dict[str, object] = {}
    for name in registry.names():
        try:
            results = _process_source_with_weights(registry.get(name), ranking, source_config, runtime_config["ranking_weights"])
            alert_attempts = 0
            alert_results: list[dict] = []
            for result in results:
                if not result.get("keep") or not result.get("selected"):
                    continue
                alert_attempts += 1
                alert_results.append(maybe_alert(result))
            error = None
        except Exception as exc:  # pragma: no cover - best-effort resilience
            results = []
            alert_attempts = 0
            alert_results = []
            error = str(exc)
        summary[name] = {
            "count": len(results),
            "kept": len([result for result in results if result.get("keep")]),
            "selected": len([result for result in results if result.get("selected")]),
            "alert_attempts": alert_attempts,
            "alert_sent": len([result for result in alert_results if result.get("alert_sent")]),
            "top_score": max((result["score"] for result in results), default=0),
            "skipped_recently_scored": len([result for result in results if result.get("skipped_reason") == "recently_scored"]),
            "error": error,
        }
    return summary


@celery_app.task(name="marshallbot.run_daily_digest", bind=True, autoretry_for=(Exception,), retry_backoff=True)
def run_daily_digest(self, limit: int = 30) -> dict:
    record_runtime_heartbeat(role="worker")
    ranking = list_ranking_dashboard(limit=limit)
    return {
        "limit": limit,
        "top_projects": ranking,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@celery_app.task(
    name="marshallbot.capture_website_snapshot",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def capture_website_snapshot(self, project_id: int, website_url: str) -> dict:
    record_runtime_heartbeat(role="worker")
    snapshot = enrich_website(website_url)
    store_website_snapshot(project_id, snapshot)
    return {
        "project_id": project_id,
        "url": website_url,
        "html_hash": snapshot.get("html_hash"),
        "text_hash": snapshot.get("text_hash"),
    }


@celery_app.task(name="marshallbot.reprocess_project", bind=True, autoretry_for=(Exception,), retry_backoff=True)
def reprocess_project_task(self, project_id: int) -> dict:
    record_runtime_heartbeat(role="worker")
    from app.db.queries import get_project_details
    from app.services.orchestration import reprocess_project

    source_config = SourceConfig.load()
    project = get_project_details(project_id)
    if not project:
        return {"ok": False, "reason": "not_found", "project_id": project_id}

    ranking = RankingConfig(
        min_score_to_alert=float(load_runtime_config()["min_score_to_alert"]),
        daily_alert_limit=int(load_runtime_config()["daily_alert_limit"]),
    )
    result = reprocess_project(
        project,
        source_config,
        ranking,
        enrich_websites=True,
    )
    return {"ok": True, "project_id": project_id, "result": result}


@celery_app.task(name="marshallbot.update_runtime_heartbeat", bind=True, autoretry_for=(Exception,), retry_backoff=True)
def update_runtime_heartbeat(self, role: str = "beat") -> dict:
    return record_runtime_heartbeat(role=role)
