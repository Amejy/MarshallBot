from __future__ import annotations

from app.core.runtime_config import load_runtime_config, list_runtime_config_history
from app.core.source_config import SourceConfig
from app.services.admin_dashboard import build_dashboard_payload
from app.services.runtime_health import get_runtime_health


def build_export_payload(limit: int = 20) -> dict:
    source_config = SourceConfig.load()
    runtime_config = load_runtime_config()
    try:
        dashboard = build_dashboard_payload(limit=limit)
        error = None
    except Exception as exc:
        dashboard = {
            "error": str(exc),
            "summary": {},
            "activity": {},
            "ranking": [],
            "today": [],
            "alerts": [],
            "alert_health": {"totals": {"sent": 0, "pending": 0, "failed": 0, "total": 0}, "issues": []},
            "sources": [],
            "trends": [],
            "movers": [],
            "health": [],
        }
        error = str(exc)
    payload = {
        "dashboard": dashboard,
        "runtime_config": runtime_config,
        "runtime_config_history": list_runtime_config_history(limit=limit),
        "runtime_health": get_runtime_health(),
        "source_config": {
            "launchpads": source_config.launchpads,
            "telegram_channels": source_config.telegram_channels,
            "keywords": source_config.keywords,
            "blacklisted_domains": source_config.blacklisted_domains,
            "blacklisted_telegram": source_config.blacklisted_telegram,
            "trusted_sources": source_config.trusted_sources,
        },
    }
    if error:
        payload["error"] = error
    return payload
