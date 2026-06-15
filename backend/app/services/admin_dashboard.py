from __future__ import annotations

from app.db.queries import dashboard_activity, dashboard_summary, list_alert_health, list_ranking_dashboard, list_recent_alerts, list_recent_social_profiles, list_source_health, list_source_movers, list_source_trends, list_sources, list_top_today_projects
from app.core.runtime_config import load_runtime_config, list_runtime_config_history
from app.core.source_config import build_source_coverage_summary, build_source_selection_summary, SourceConfig
from app.services.runtime_health import get_runtime_health
from app.services.source_templates import list_source_templates
from app.services.telegram_research import TelegramResearchConfig, build_telegram_onboarding


def build_dashboard_payload(limit: int = 20, source_config: SourceConfig | None = None) -> dict:
    source_config = source_config or SourceConfig.load()
    source_templates = list_source_templates()
    try:
        return {
            "summary": dashboard_summary(),
            "activity": dashboard_activity(),
            "ranking": list_ranking_dashboard(limit=limit),
            "today": list_top_today_projects(limit=limit),
            "alerts": list_recent_alerts(limit=limit),
            "social_profiles": list_recent_social_profiles(limit=limit),
            "alert_health": list_alert_health(limit=limit),
            "sources": list_sources(limit=limit),
            "trends": list_source_trends(limit=limit),
            "movers": list_source_movers(limit=limit),
            "health": list_source_health(limit=limit),
            "runtime_health": get_runtime_health(),
            "runtime_config": load_runtime_config(),
            "runtime_config_history": list_runtime_config_history(limit=10),
            "source_templates": source_templates,
            "source_selection": build_source_selection_summary(source_config),
            "source_coverage": build_source_coverage_summary(source_config, templates_count=len(source_templates)),
            "social_accounts": list(source_config.social_accounts),
            "telegram_onboarding": build_telegram_onboarding(
                [str(channel) for item in source_config.telegram_channels for channel in (item.get("channels") or item.get("usernames") or [item.get("name")]) if str(channel).strip()],
                chain="solana",
                name_prefix="telegram-research",
            ),
            "telegram_research": TelegramResearchConfig().status(),
        }
    except Exception as exc:
        return {
            "error": str(exc),
            "summary": {},
            "activity": {},
            "ranking": [],
            "today": [],
            "alerts": [],
            "social_profiles": [],
            "alert_health": {"totals": {"sent": 0, "pending": 0, "failed": 0, "total": 0}, "issues": []},
            "sources": [],
            "trends": [],
            "movers": [],
            "health": [],
            "runtime_health": get_runtime_health(),
            "runtime_config": load_runtime_config(),
            "runtime_config_history": list_runtime_config_history(limit=10),
            "source_templates": source_templates,
            "source_selection": build_source_selection_summary(source_config),
            "source_coverage": build_source_coverage_summary(source_config, templates_count=len(source_templates)),
            "social_accounts": list(source_config.social_accounts),
            "telegram_onboarding": build_telegram_onboarding(
                [str(channel) for item in source_config.telegram_channels for channel in (item.get("channels") or item.get("usernames") or [item.get("name")]) if str(channel).strip()],
                chain="solana",
                name_prefix="telegram-research",
            ),
            "telegram_research": TelegramResearchConfig().status(),
        }
