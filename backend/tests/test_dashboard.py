from app.services.sources import StaticDiscoverySource
from app.services.ranking import RankingConfig
from app.services.orchestration import process_source
from app.core.source_config import SourceConfig


def test_dashboard_summary_endpoint_shape(monkeypatch) -> None:
    from app.db import queries

    monkeypatch.setattr(
        queries,
        "dashboard_summary",
        lambda: {
            "total_projects": 10,
            "qualified_projects": 4,
            "new_projects": 3,
            "rejected_projects": 1,
            "scored_projects": 7,
            "active_projects": 5,
            "skipped_recently_scored": 2,
        },
    )
    summary = queries.dashboard_summary()
    assert summary["total_projects"] == 10


def test_build_dashboard_payload_includes_health(monkeypatch) -> None:
    from app.services import admin_dashboard

    monkeypatch.setattr(
        admin_dashboard,
        "SourceConfig",
        type(
            "Cfg",
            (),
            {
                "load": classmethod(
                    lambda cls: SourceConfig(
                        launchpads=[{"name": "pump-fun"}],
                        telegram_channels=[{"name": "alpha-meme-watch"}],
                        social_accounts=[{"name": "alpha-x-watch"}],
                        trusted_sources=["pump-fun"],
                    )
                )
            },
        ),
    )
    monkeypatch.setattr(admin_dashboard, "dashboard_summary", lambda: {"total_projects": 1})
    monkeypatch.setattr(admin_dashboard, "dashboard_activity", lambda: {"discovered_today": 1})
    monkeypatch.setattr(admin_dashboard, "list_ranking_dashboard", lambda limit=20: [])
    monkeypatch.setattr(admin_dashboard, "list_top_today_projects", lambda limit=20: [])
    monkeypatch.setattr(admin_dashboard, "list_recent_alerts", lambda limit=20: [{"canonical_name": "Alpha"}])
    monkeypatch.setattr(admin_dashboard, "list_recent_social_profiles", lambda limit=20: [{"canonical_name": "Alpha", "platform": "x"}])
    monkeypatch.setattr(admin_dashboard, "list_alert_health", lambda limit=20: {"totals": {"sent": 1, "pending": 1, "failed": 0, "total": 2}, "issues": []})
    monkeypatch.setattr(admin_dashboard, "list_sources", lambda limit=20: [])
    monkeypatch.setattr(admin_dashboard, "list_source_trends", lambda limit=20: [])
    monkeypatch.setattr(admin_dashboard, "list_source_movers", lambda limit=20: [{"account_identifier": "pump.fun", "momentum_score": 12.5}])
    monkeypatch.setattr(admin_dashboard, "list_source_health", lambda limit=20: [{"account_identifier": "pump.fun"}])
    monkeypatch.setattr(admin_dashboard, "list_source_templates", lambda: [{"mode": "rss", "label": "RSS feed"}])
    monkeypatch.setattr(admin_dashboard, "TelegramResearchConfig", lambda: type("Cfg", (), {"status": lambda self: {"ready": False, "missing_fields": ["telegram_api_id"]}})())
    monkeypatch.setattr(
        admin_dashboard,
        "get_runtime_health",
        lambda: {"beat": {"healthy": True}, "worker": {"healthy": True}, "worker_count": 1, "workers": []},
    )
    monkeypatch.setattr(
        admin_dashboard,
        "load_runtime_config",
        lambda: {"daily_alert_limit": 30, "min_score_to_alert": 75, "ranking_weights": {"freshness": 0.2}},
    )
    monkeypatch.setattr(
        admin_dashboard,
        "list_runtime_config_history",
        lambda limit=10: [{"changed_at": "2026-06-11T11:15:00Z", "changed_by": "dashboard", "daily_alert_limit": 30, "min_score_to_alert": 75}],
    )

    payload = admin_dashboard.build_dashboard_payload()
    assert "health" in payload
    assert "alerts" in payload
    assert "social_profiles" in payload
    assert "alert_health" in payload
    assert "runtime_health" in payload
    assert "runtime_config" in payload
    assert "runtime_config_history" in payload
    assert "movers" in payload
    assert "source_templates" in payload
    assert "source_selection" in payload
    assert "source_coverage" in payload
    assert "social_accounts" in payload
    assert "telegram_onboarding" in payload
    assert "telegram_research" in payload
    assert payload["health"][0]["account_identifier"] == "pump.fun"
    assert payload["movers"][0]["account_identifier"] == "pump.fun"
    assert payload["source_templates"][0]["mode"] == "rss"
    assert payload["social_accounts"][0]["name"] == "alpha-x-watch"
    assert payload["social_profiles"][0]["platform"] == "x"
    assert payload["telegram_research"]["missing_fields"] == ["telegram_api_id"]


def test_build_dashboard_payload_falls_back_on_db_error(monkeypatch) -> None:
    from app.services import admin_dashboard

    monkeypatch.setattr(
        admin_dashboard,
        "dashboard_summary",
        lambda: (_ for _ in ()).throw(RuntimeError("db unavailable")),
    )
    monkeypatch.setattr(
        admin_dashboard,
        "get_runtime_health",
        lambda: {"beat": {"healthy": True}, "worker": {"healthy": True}, "worker_count": 1, "workers": []},
    )
    monkeypatch.setattr(admin_dashboard, "load_runtime_config", lambda: {"daily_alert_limit": 30, "min_score_to_alert": 75, "ranking_weights": {"freshness": 0.2}})
    monkeypatch.setattr(admin_dashboard, "list_runtime_config_history", lambda limit=10: [])
    monkeypatch.setattr(admin_dashboard, "list_source_templates", lambda: [{"mode": "rss", "label": "RSS feed"}])
    monkeypatch.setattr(admin_dashboard, "list_recent_social_profiles", lambda limit=20: [])

    payload = admin_dashboard.build_dashboard_payload()

    assert payload["error"] == "db unavailable"
    assert payload["ranking"] == []
    assert payload["source_templates"][0]["mode"] == "rss"


def test_process_source_marks_selected(monkeypatch) -> None:
    source = StaticDiscoverySource(
        [
            {
                "canonical_name": "Alpha",
                "chain": "solana",
                "website_url": "https://example.com",
                "telegram_url": "https://t.me/example",
                "source_type": "demo",
                "source_name": "demo",
            }
        ]
    )
    results = process_source(source, RankingConfig(min_score_to_alert=0), enrich_websites=False)
    assert results[0]["selected"] is True
