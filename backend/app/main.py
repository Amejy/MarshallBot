from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.source_config import SourceConfig, build_source_coverage_summary, build_source_selection_summary
from app.core.logging import configure_logging
from app.services.ranking import RankingConfig
from app.services.orchestration import process_source
from app.services.registry import build_default_registry
from app.services.telegram_research import TelegramResearchConfig, build_telegram_onboarding
from app.services.telegram import TelegramBotClient
from app.services.alerting import build_alert_message
from app.db.queries import get_latest_project_score, get_project_details, get_source_health_detail, list_ranking_dashboard, list_recent_alerts, list_recent_social_profiles, list_source_health, list_source_movers, list_sources, list_top_projects, list_source_recent_projects, search_projects, list_source_trends, list_top_today_projects
from app.db.repository import get_source_account, list_source_account_history, set_source_status, set_source_trust
from app.services.orchestration import reprocess_project
from app.db.queries import dashboard_summary
from app.services.backfill import backfill_source
from app.services.admin_dashboard import build_dashboard_payload
from app.services.export import build_export_payload
from app.services.source_templates import list_source_templates
from app.core.runtime_config import apply_runtime_config, load_runtime_config, list_runtime_config_history
from app.services.runtime_health import get_runtime_health
import app.tasks as task_helpers

configure_logging()
app = FastAPI(title="MarshallBot API", version="0.1.0")
source_config = SourceConfig.load()
registry = build_default_registry(source_config)
DASHBOARD_FILE = Path(__file__).resolve().parent / "static" / "dashboard.html"


def _summarize_trust_movement(history: list[dict]) -> dict[str, object]:
    for item in history:
        trust_before = item.get("trust_before")
        trust_after = item.get("trust_after")
        if trust_before is None or trust_after is None:
            continue
        delta = float(trust_after) - float(trust_before)
        if delta > 0:
            direction = "up"
        elif delta < 0:
            direction = "down"
        else:
            direction = "flat"
        return {
            "trust_movement": delta,
            "trust_movement_direction": direction,
            "trust_movement_changed_at": item.get("changed_at"),
        }
    return {
        "trust_movement": 0.0,
        "trust_movement_direction": "flat",
        "trust_movement_changed_at": None,
    }


def _configured_telegram_channels() -> list[str]:
    channels: list[str] = []
    for channel in source_config.telegram_channels:
        collected_for_entry = False
        for key in ("channels", "usernames"):
            value = channel.get(key) or []
            if isinstance(value, str):
                value = [value]
            normalized_values = [str(item).strip() for item in value if str(item).strip()]
            if normalized_values:
                channels.extend(normalized_values)
                collected_for_entry = True
        name = str(channel.get("name", "")).strip()
        if name and not collected_for_entry:
            channels.append(name)
    return channels


def _safe_payload(loader, fallback: dict[str, object]) -> dict[str, object]:
    try:
        return loader()
    except Exception as exc:
        return {**fallback, "error": str(exc)}


def _latest_real_alert_project() -> tuple[dict[str, object] | None, float | None, str | None]:
    project_sources = (
        ("top_today", list_top_today_projects),
        ("ranking_dashboard", list_ranking_dashboard),
        ("top_projects", list_top_projects),
    )
    for source_name, loader in project_sources:
        projects = loader(limit=1)
        if not projects:
            continue
        project = dict(projects[0])
        score = project.get("current_score")
        if score is None:
            score = project.get("best_score")
        try:
            score_value = float(score) if score is not None else None
        except (TypeError, ValueError):
            score_value = None
        return project, score_value, source_name
    return None, None, None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "marshallbot",
        "environment": settings.environment,
    }


@app.get("/dashboard")
def dashboard_page() -> FileResponse:
    return FileResponse(DASHBOARD_FILE)


@app.get("/config")
def config() -> dict[str, object]:
    runtime_config = load_runtime_config()
    telegram_research_config = TelegramResearchConfig()
    ranking = RankingConfig(
        min_score_to_alert=float(runtime_config["min_score_to_alert"]),
        daily_alert_limit=int(runtime_config["daily_alert_limit"]),
    )
    return {
        "daily_alert_limit": ranking.daily_alert_limit,
        "min_score_to_alert": ranking.min_score_to_alert,
        "ranking_weights": runtime_config["ranking_weights"],
        "runtime_config": runtime_config,
        "telegram_configured": bool(settings.telegram_bot_token and settings.telegram_chat_id),
        "telegram_research_configured": telegram_research_config.ready,
        "telegram_research": telegram_research_config.status(),
        "source_config": {
            "launchpads": len(source_config.launchpads),
            "telegram_channels": len(source_config.telegram_channels),
            "social_accounts": len(source_config.social_accounts),
            "keywords": source_config.keywords,
            "blacklisted_domains": source_config.blacklisted_domains,
            "blacklisted_telegram": source_config.blacklisted_telegram,
            "trusted_sources": source_config.trusted_sources,
        },
        "source_selection": build_source_selection_summary(source_config),
        "source_coverage": build_source_coverage_summary(source_config, templates_count=len(list_source_templates())),
        "telegram_onboarding": build_telegram_onboarding(_configured_telegram_channels(), chain="solana", name_prefix="telegram-research"),
    }


@app.get("/collectors")
def collectors() -> dict[str, object]:
    return {"collectors": registry.names()}


@app.get("/demo/discovery/{collector_name}")
def demo_discovery(collector_name: str) -> dict[str, object]:
    source = registry.get(collector_name)
    ranking = RankingConfig(
        min_score_to_alert=settings.min_score_to_alert,
        daily_alert_limit=settings.daily_alert_limit,
    )
    results = process_source(source, ranking, source_config=source_config, enrich_websites=False)
    return {
        "collector": collector_name,
        "results": results,
        "kept": [item for item in results if item.get("keep")],
    }


@app.get("/projects/top")
def top_projects(limit: int = 30) -> dict[str, object]:
    return _safe_payload(lambda: {"items": list_top_projects(limit=limit)}, {"items": []})


@app.get("/projects/top-today")
def top_today_projects(limit: int = 30) -> dict[str, object]:
    return _safe_payload(lambda: {"items": list_top_today_projects(limit=limit)}, {"items": []})


@app.get("/projects/search")
def search_projects_endpoint(q: str, limit: int = 20) -> dict[str, object]:
    return _safe_payload(lambda: {"query": q, "items": search_projects(q, limit=limit)}, {"query": q, "items": []})


@app.get("/alerts/recent")
def recent_alerts(limit: int = 30) -> dict[str, object]:
    return _safe_payload(lambda: {"items": list_recent_alerts(limit=limit)}, {"items": []})


@app.post("/alerts/test")
def send_test_alert() -> dict[str, object]:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return {"ok": False, "reason": "telegram_not_configured"}

    project, score, source_name = _latest_real_alert_project()
    if not project or score is None:
        return {
            "ok": False,
            "reason": "no_real_projects_found",
            "detail": "No scored projects are available yet. Let discovery run or backfill a source, then retry.",
        }

    project["score_explanations"] = (
        project.get("score_explanations")
        or project.get("score_reasons", {}).get("explanations", [])
        or [
            "Latest real project from the database",
            f"Selected from {source_name}",
        ]
    )
    message = build_alert_message(project, score)
    import asyncio

    result = asyncio.run(TelegramBotClient().send_message(settings.telegram_chat_id, message))
    return {
        "ok": True,
        "result": result,
        "project": {
            "id": project.get("id"),
            "canonical_name": project.get("canonical_name"),
            "chain": project.get("chain"),
            "website_url": project.get("website_url"),
            "telegram_url": project.get("telegram_url"),
            "launch_source": project.get("launch_source"),
            "current_score": project.get("current_score"),
            "best_score": project.get("best_score"),
            "selected_from": source_name,
        },
    }


@app.post("/alerts/{alert_id}/retry")
def retry_alert_delivery(alert_id: int) -> dict[str, object]:
    result = task_helpers.retry_alert_delivery(alert_id)
    return result


@app.get("/projects/{project_id}")
def project_detail(project_id: int) -> dict[str, object]:
    return _safe_payload(lambda: {"project": get_project_details(project_id)}, {"project": None})


@app.get("/projects/{project_id}/explain")
def project_explain(project_id: int) -> dict[str, object]:
    def _load() -> dict[str, object]:
        project = get_project_details(project_id)
        score = get_latest_project_score(project_id)
        if not project:
            return {"ok": False, "reason": "not_found", "project_id": project_id}
        source = None
        trust_history = []
        trust_summary = None
        if project.get("launch_source"):
            source = get_source_account(str(project.get("launch_source")))
            trust_history = list_source_account_history(str(project.get("launch_source")), limit=10)
            trust_summary = _summarize_trust_movement(trust_history)
        return {
            "ok": True,
            "project_id": project_id,
            "project": {
                "canonical_name": project.get("canonical_name"),
                "chain": project.get("chain"),
                "website_url": project.get("website_url"),
                "telegram_url": project.get("telegram_url"),
                "launch_source": project.get("launch_source"),
                "status": project.get("status"),
                "current_score": project.get("current_score"),
            },
            "source": source,
            "source_history": trust_history,
            "source_trust_movement": trust_summary,
            "latest_score": score,
            "score_explanations": (score.get("score_reasons", {}) if score else {}).get("explanations", []),
        }

    return _safe_payload(_load, {"ok": False, "reason": "db_unavailable", "project_id": project_id, "project": None})


@app.get("/dashboard/ranking")
def ranking_dashboard(limit: int = 30) -> dict[str, object]:
    return _safe_payload(lambda: {"limit": limit, "items": list_ranking_dashboard(limit=limit)}, {"limit": limit, "items": []})


@app.get("/dashboard/summary")
def dashboard() -> dict[str, object]:
    return _safe_payload(dashboard_summary, {})


@app.get("/dashboard/activity")
def dashboard_activity_view() -> dict[str, object]:
    from app.db.queries import dashboard_activity
    return _safe_payload(dashboard_activity, {})


@app.get("/api/dashboard")
def api_dashboard(limit: int = 20) -> dict[str, object]:
    return build_dashboard_payload(limit=limit, source_config=source_config)


@app.get("/config/source-selection")
def source_selection_view() -> dict[str, object]:
    return build_source_selection_summary(source_config)


@app.get("/config/source-coverage")
def source_coverage_view() -> dict[str, object]:
    return build_source_coverage_summary(source_config, templates_count=len(list_source_templates()))


@app.get("/config/telegram-onboarding")
def telegram_onboarding_view() -> dict[str, object]:
    return build_telegram_onboarding(_configured_telegram_channels(), chain="solana", name_prefix="telegram-research")


@app.get("/export/state")
def export_state(limit: int = 20) -> dict[str, object]:
    return build_export_payload(limit=limit)


@app.get("/sources")
def sources() -> dict[str, object]:
    return {
        "launchpads": source_config.launchpads,
        "telegram_channels": source_config.telegram_channels,
        "social_accounts": source_config.social_accounts,
        "keywords": source_config.keywords,
        "blacklisted_domains": source_config.blacklisted_domains,
        "blacklisted_telegram": source_config.blacklisted_telegram,
        "trusted_sources": source_config.trusted_sources,
    }


@app.get("/sources/templates")
def source_templates() -> dict[str, object]:
    return {"items": list_source_templates()}


@app.get("/config/telegram-research")
def telegram_research_config_view() -> dict[str, object]:
    config = TelegramResearchConfig()
    return {"telegram_research": config.status()}


@app.get("/sources/accounts")
def sources_accounts(limit: int = 100, status: str | None = None) -> dict[str, object]:
    return _safe_payload(lambda: {"items": list_sources(limit=limit, status=status)}, {"items": []})


@app.get("/sources/accounts/{account_identifier}")
def source_account_detail(account_identifier: str) -> dict[str, object]:
    def _load() -> dict[str, object]:
        history = list_source_account_history(account_identifier, limit=10)
        return {
            "source": get_source_account(account_identifier),
            "health": get_source_health_detail(account_identifier),
            "recent_projects": list_source_recent_projects(account_identifier, limit=5),
            "history": history,
            "trust_movement": _summarize_trust_movement(history),
        }

    return _safe_payload(
        _load,
        {
            "source": None,
            "health": None,
            "recent_projects": [],
            "history": [],
            "trust_movement": {"trust_movement": 0.0, "trust_movement_direction": "flat", "trust_movement_changed_at": None},
        },
    )


@app.post("/sources/accounts/{account_identifier}/approve")
def approve_source_account(account_identifier: str) -> dict[str, object]:
    def _load() -> dict[str, object]:
        set_source_status(account_identifier, "active", trust_level=90.0)
        return {"ok": True, "account_identifier": account_identifier, "status": "active"}

    return _safe_payload(
        _load,
        {"ok": False, "reason": "db_unavailable", "account_identifier": account_identifier, "status": "active"},
    )


@app.post("/sources/accounts/{account_identifier}/watch")
def watch_source_account(account_identifier: str) -> dict[str, object]:
    def _load() -> dict[str, object]:
        set_source_status(account_identifier, "watch")
        return {"ok": True, "account_identifier": account_identifier, "status": "watch"}

    return _safe_payload(
        _load,
        {"ok": False, "reason": "db_unavailable", "account_identifier": account_identifier, "status": "watch"},
    )


@app.post("/sources/accounts/{account_identifier}/reject")
def reject_source_account(account_identifier: str) -> dict[str, object]:
    def _load() -> dict[str, object]:
        set_source_status(account_identifier, "rejected", trust_level=0.0)
        return {"ok": True, "account_identifier": account_identifier, "status": "rejected"}

    return _safe_payload(
        _load,
        {"ok": False, "reason": "db_unavailable", "account_identifier": account_identifier, "status": "rejected"},
    )


@app.post("/sources/accounts/{account_identifier}/trust/{trust_level}")
def set_source_trust_level(account_identifier: str, trust_level: float) -> dict[str, object]:
    def _load() -> dict[str, object]:
        set_source_trust(account_identifier, trust_level)
        return {"ok": True, "account_identifier": account_identifier, "trust_level": trust_level}

    return _safe_payload(
        _load,
        {
            "ok": False,
            "reason": "db_unavailable",
            "account_identifier": account_identifier,
            "trust_level": trust_level,
        },
    )


@app.get("/projects/skipped/recent")
def recently_skipped_projects(limit: int = 100) -> dict[str, object]:
    from app.db.queries import list_recently_skipped_projects
    return _safe_payload(lambda: {"items": list_recently_skipped_projects(limit=limit)}, {"items": []})


@app.get("/social/profiles/recent")
def recent_social_profiles(limit: int = 50) -> dict[str, object]:
    return _safe_payload(lambda: {"items": list_recent_social_profiles(limit=limit)}, {"items": []})


@app.post("/projects/{project_id}/reprocess")
def reprocess_existing_project(project_id: int) -> dict[str, object]:
    def _load() -> dict[str, object]:
        project = get_project_details(project_id)
        if not project:
            return {"ok": False, "reason": "not_found", "project_id": project_id}
        ranking = RankingConfig(
            min_score_to_alert=settings.min_score_to_alert,
            daily_alert_limit=settings.daily_alert_limit,
        )
        result = reprocess_project(project, source_config, ranking, enrich_websites=True)
        return {"ok": True, "project_id": project_id, "result": result}

    return _safe_payload(_load, {"ok": False, "reason": "db_unavailable", "project_id": project_id})


@app.post("/sources/{source_name}/backfill")
def backfill_existing_source(source_name: str, limit: int = 20) -> dict[str, object]:
    def _load() -> dict[str, object]:
        ranking = RankingConfig(
            min_score_to_alert=settings.min_score_to_alert,
            daily_alert_limit=settings.daily_alert_limit,
        )
        payload = backfill_source(source_name, source_config, ranking, limit=limit)
        payload["limit"] = limit
        return payload

    return _safe_payload(_load, {"ok": False, "reason": "db_unavailable", "source_name": source_name, "limit": limit})


@app.get("/sources/trends")
def source_trends(limit: int = 50) -> dict[str, object]:
    return _safe_payload(lambda: {"items": list_source_trends(limit=limit)}, {"items": []})


@app.get("/sources/movers")
def source_movers(limit: int = 10) -> dict[str, object]:
    return _safe_payload(lambda: {"items": list_source_movers(limit=limit)}, {"items": []})


@app.get("/sources/health")
def source_health(limit: int = 50) -> dict[str, object]:
    return _safe_payload(lambda: {"items": list_source_health(limit=limit)}, {"items": []})


@app.get("/runtime/health")
def runtime_health() -> dict[str, object]:
    return get_runtime_health()


@app.get("/config/runtime")
def runtime_config_view() -> dict[str, object]:
    return _safe_payload(
        lambda: {
            "runtime_config": load_runtime_config(),
            "history": list_runtime_config_history(limit=20),
        },
        {"runtime_config": load_runtime_config(), "history": []},
    )


@app.get("/config/runtime/history")
def runtime_config_history(limit: int = 20) -> dict[str, object]:
    return _safe_payload(lambda: {"items": list_runtime_config_history(limit=limit)}, {"items": []})


@app.post("/config/runtime")
def update_runtime_config(payload: dict[str, object]) -> dict[str, object]:
    updated_by = str(payload.get("updated_by", "dashboard"))
    runtime_config = apply_runtime_config({**payload, "updated_by": updated_by})
    return {"ok": True, "runtime_config": runtime_config, "updated_by": updated_by}
