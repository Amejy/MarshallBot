from pathlib import Path

import app.main as main


def test_source_moderation_endpoints_call_repository(monkeypatch) -> None:
    calls: list[tuple[str, str, float | None]] = []

    def fake_set_source_status(account_identifier: str, status: str, trust_level: float | None = None) -> None:
        calls.append((account_identifier, status, trust_level))

    def fake_set_source_trust(account_identifier: str, trust_level: float) -> None:
        calls.append((account_identifier, "trust", trust_level))

    monkeypatch.setattr(main, "set_source_status", fake_set_source_status)
    monkeypatch.setattr(main, "set_source_trust", fake_set_source_trust)

    approve = main.approve_source_account("pump.fun")
    watch = main.watch_source_account("pump.fun")
    reject = main.reject_source_account("pump.fun")
    trust = main.set_source_trust_level("pump.fun", 77.5)

    assert approve["status"] == "active"
    assert watch["status"] == "watch"
    assert reject["status"] == "rejected"
    assert trust["trust_level"] == 77.5
    assert calls == [
        ("pump.fun", "active", 90.0),
        ("pump.fun", "watch", None),
        ("pump.fun", "rejected", 0.0),
        ("pump.fun", "trust", 77.5),
    ]


def test_source_moderation_endpoints_fall_back_when_db_fails(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(main, "set_source_status", boom)
    monkeypatch.setattr(main, "set_source_trust", boom)

    approve = main.approve_source_account("pump.fun")
    watch = main.watch_source_account("pump.fun")
    reject = main.reject_source_account("pump.fun")
    trust = main.set_source_trust_level("pump.fun", 77.5)

    assert approve["ok"] is False
    assert approve["reason"] == "db_unavailable"
    assert watch["status"] == "watch"
    assert reject["status"] == "rejected"
    assert trust["trust_level"] == 77.5


def test_source_detail_endpoint_uses_repository(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "get_source_account",
        lambda account_identifier: {"account_identifier": account_identifier, "status": "active"},
    )
    monkeypatch.setattr(
        main,
        "get_source_health_detail",
        lambda account_identifier: {
            "account_identifier": account_identifier,
            "platform": "launchpad",
            "status": "active",
            "trust_level": 92,
            "project_count": 42,
            "qualified_count": 18,
            "avg_score": 83.4,
            "health_score": 96.2,
        },
    )
    monkeypatch.setattr(
        main,
        "list_source_recent_projects",
        lambda account_identifier, limit=5: [
            {"id": 1, "canonical_name": "Alpha", "current_score": 91.5, "status": "qualified", "last_seen_at": "2026-06-11T11:00:00Z"}
        ],
    )
    monkeypatch.setattr(
        main,
        "list_source_account_history",
        lambda account_identifier, limit=10: [
            {
                "changed_at": "2026-06-11T11:05:00Z",
                "changed_by": "dashboard",
                "action": "trust_updated",
                "status_before": "watch",
                "status_after": "watch",
                "trust_before": 70,
                "trust_after": 92,
                "note": None,
            }
        ],
    )

    response = main.source_account_detail("pump.fun")

    assert response["source"]["account_identifier"] == "pump.fun"
    assert response["health"]["health_score"] == 96.2
    assert response["recent_projects"][0]["canonical_name"] == "Alpha"
    assert response["history"][0]["action"] == "trust_updated"
    assert response["trust_movement"]["trust_movement"] == 22
    assert response["trust_movement"]["trust_movement_direction"] == "up"


def test_project_explain_endpoint_returns_score_details(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "get_project_details",
        lambda project_id: {
            "canonical_name": "Alpha",
            "chain": "solana",
            "website_url": "https://example.com",
            "telegram_url": "https://t.me/alpha",
            "launch_source": "pump.fun",
            "status": "qualified",
            "current_score": 91.5,
        },
    )
    monkeypatch.setattr(
        main,
        "get_source_account",
        lambda account_identifier: {"account_identifier": account_identifier, "trust_level": 93},
    )
    monkeypatch.setattr(
        main,
        "list_source_account_history",
        lambda account_identifier, limit=10: [
            {
                "changed_at": "2026-06-11T11:05:00Z",
                "changed_by": "dashboard",
                "action": "trust_adjusted",
                "status_before": "active",
                "status_after": "active",
                "trust_before": 88,
                "trust_after": 93,
                "note": None,
            }
        ],
    )
    monkeypatch.setattr(
        main,
        "get_latest_project_score",
        lambda project_id: {
            "score_reasons": {"explanations": ["Telegram link present", "Website looks complete"]},
            "model_version": "v1",
            "scored_at": "2026-06-11T10:00:00Z",
        },
    )

    body = main.project_explain(42)

    assert body["ok"] is True
    assert body["project"]["canonical_name"] == "Alpha"
    assert body["source"]["trust_level"] == 93
    assert body["source_trust_movement"]["trust_movement"] == 5
    assert body["score_explanations"][0] == "Telegram link present"


def test_project_search_endpoint_uses_repository(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "search_projects",
        lambda q, limit=20: [{
            "id": 7,
            "canonical_name": f"{q} Alpha",
            "current_score": 88,
            "chain": "solana",
            "launch_source": "pump.fun",
            "status": "qualified",
            "source_trust_level": 91,
            "source_trust_movement": 3.5,
            "source_trust_movement_direction": "up",
        }],
    )

    body = main.search_projects_endpoint("Alpha", limit=5)

    assert body["query"] == "Alpha"
    assert body["items"][0]["canonical_name"] == "Alpha Alpha"
    assert body["items"][0]["source_trust_movement_direction"] == "up"


def test_source_selection_endpoint_reports_active_sources(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "build_source_selection_summary",
        lambda source_config: {
            "launchpads": {"requested": ["pump-fun"], "active": ["pump-fun"], "count": 1, "unknown": []},
            "telegram_channels": {"requested": ["alpha-meme-watch"], "active": ["alpha-meme-watch"], "count": 1, "unknown": []},
            "keywords": ["meme"],
            "blacklisted_domains": [],
            "blacklisted_telegram": [],
            "trusted_sources": ["pump-fun"],
        },
    )

    body = main.source_selection_view()

    assert body["launchpads"]["count"] == 1
    assert body["telegram_channels"]["active"] == ["alpha-meme-watch"]


def test_source_coverage_endpoint_reports_ready(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "build_source_coverage_summary",
        lambda source_config, templates_count=0: {
            "ready": True,
            "active_sources": 2,
            "active_launchpads": 1,
            "active_telegram_channels": 1,
            "source_templates": templates_count,
            "keywords": 2,
            "trusted_sources": 1,
            "unknown_sources": 0,
        },
    )

    body = main.source_coverage_view()
    assert body["ready"] is True
    assert body["active_sources"] == 2


def test_dashboard_page_points_at_packaged_file() -> None:
    response = main.dashboard_page()

    assert Path(main.DASHBOARD_FILE).exists()
    assert Path(response.path) == Path(main.DASHBOARD_FILE)


def test_recent_social_profiles_endpoint_uses_repository(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "list_recent_social_profiles",
        lambda limit=50: [
            {
                "id": 1,
                "platform": "x",
                "url": "https://x.com/example",
                "canonical_name": "Alpha",
                "chain": "solana",
            }
        ],
    )

    body = main.recent_social_profiles(limit=5)

    assert body["items"][0]["platform"] == "x"
    assert body["items"][0]["canonical_name"] == "Alpha"


def test_top_projects_endpoint_falls_back_when_db_fails(monkeypatch) -> None:
    monkeypatch.setattr(main, "list_top_projects", lambda limit=30: (_ for _ in ()).throw(RuntimeError("db unavailable")))

    body = main.top_projects(limit=5)

    assert body["items"] == []
    assert body["error"] == "db unavailable"


def test_telegram_onboarding_endpoint_returns_snippet(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "build_telegram_onboarding",
        lambda channels, chain="solana", name_prefix="telegram-research": {
            "chain": chain,
            "requested": channels,
            "channels": ["AlphaMemeWatch"],
            "invalid_channels": [],
            "count": 1,
            "example_json": {
                "name": name_prefix,
                "enabled": True,
                "mode": "research",
                "chain": chain,
                "limit": 100,
                "channels": ["AlphaMemeWatch"],
            },
        },
    )

    body = main.telegram_onboarding_view()

    assert body["count"] == 1
    assert body["channels"] == ["AlphaMemeWatch"]


def test_reprocess_and_backfill_endpoints_fall_back_when_db_fails(monkeypatch) -> None:
    monkeypatch.setattr(main, "get_project_details", lambda project_id: (_ for _ in ()).throw(RuntimeError("db unavailable")))
    monkeypatch.setattr(main, "backfill_source", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("db unavailable")))

    reprocess = main.reprocess_existing_project(10)
    backfill = main.backfill_existing_source("pump.fun", limit=4)

    assert reprocess["ok"] is False
    assert reprocess["reason"] == "db_unavailable"
    assert reprocess["project_id"] == 10
    assert backfill["ok"] is False
    assert backfill["reason"] == "db_unavailable"
    assert backfill["source_name"] == "pump.fun"
    assert backfill["limit"] == 4


def test_test_alert_endpoint_sends_message(monkeypatch) -> None:
    sent: list[tuple[str, str]] = []

    class FakeTelegramBotClient:
        def __init__(self, token: str | None = None) -> None:
            self.token = token

        async def send_message(self, chat_id: str, text: str) -> dict:
            sent.append((chat_id, text))
            return {"ok": True, "result": {"message_id": 123}}

    monkeypatch.setattr(main, "TelegramBotClient", FakeTelegramBotClient)
    monkeypatch.setattr(main.settings, "telegram_bot_token", "token")
    monkeypatch.setattr(main.settings, "telegram_chat_id", "123456")
    monkeypatch.setattr(
        main,
        "list_top_today_projects",
        lambda limit=1: [
            {
                "id": 42,
                "canonical_name": "Alpha Wolf",
                "chain": "solana",
                "website_url": "https://alphawolf.example",
                "telegram_url": "https://t.me/alphawolf",
                "launch_source": "pump.fun",
                "current_score": 91.2,
                "best_score": 94.1,
                "score_reasons": {"explanations": ["Telegram link present", "Website quality strong"]},
            }
        ],
    )

    response = main.send_test_alert()

    assert response["ok"] is True
    assert sent
    assert sent[0][0] == "123456"
    assert "Alpha Wolf" in sent[0][1]
    assert "alphawolf.example" in sent[0][1]
    assert "t.me/alphawolf" in sent[0][1]


def test_test_alert_endpoint_reports_when_no_real_projects_exist(monkeypatch) -> None:
    monkeypatch.setattr(main, "list_top_today_projects", lambda limit=1: [])
    monkeypatch.setattr(main, "list_ranking_dashboard", lambda limit=1: [])
    monkeypatch.setattr(main, "list_top_projects", lambda limit=1: [])
    monkeypatch.setattr(main.settings, "telegram_bot_token", "token")
    monkeypatch.setattr(main.settings, "telegram_chat_id", "123456")

    response = main.send_test_alert()

    assert response["ok"] is False
    assert response["reason"] == "no_real_projects_found"


def test_retry_alert_endpoint_delegates(monkeypatch) -> None:
    monkeypatch.setattr(
        main.task_helpers,
        "retry_alert_delivery",
        lambda alert_id: {"ok": True, "alert_id": alert_id, "delivery_status": "sent"},
    )

    body = main.retry_alert_delivery(17)

    assert body["ok"] is True
    assert body["alert_id"] == 17


def test_runtime_health_endpoint_uses_service(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "get_runtime_health",
        lambda: {"beat": {"healthy": True}, "worker": {"healthy": True}, "worker_count": 1, "workers": []},
    )

    body = main.runtime_health()

    assert body["beat"]["healthy"] is True
    assert body["worker_count"] == 1


def test_runtime_config_endpoints_use_service(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "load_runtime_config",
        lambda: {"daily_alert_limit": 30, "min_score_to_alert": 75, "ranking_weights": {"freshness": 0.2}},
    )
    monkeypatch.setattr(
        main,
        "list_runtime_config_history",
        lambda limit=20: [{"changed_by": "dashboard", "daily_alert_limit": 30, "min_score_to_alert": 75}],
    )
    monkeypatch.setattr(
        main,
        "apply_runtime_config",
        lambda payload: {"daily_alert_limit": 25, "min_score_to_alert": 82, "ranking_weights": {"freshness": 0.3}},
    )

    current = main.runtime_config_view()
    history = main.runtime_config_history()
    updated = main.update_runtime_config({"min_score_to_alert": 82})

    assert current["runtime_config"]["daily_alert_limit"] == 30
    assert len(current["history"]) == 1
    assert history["items"][0]["changed_by"] == "dashboard"
    assert updated["ok"] is True
    assert updated["runtime_config"]["min_score_to_alert"] == 82


def test_telegram_research_config_endpoint_returns_status(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "TelegramResearchConfig",
        lambda: type(
            "Cfg",
            (),
            {
                "status": lambda self: {
                    "ready": False,
                    "missing_fields": ["telegram_api_id", "telegram_api_hash", "telegram_session_string"],
                    "api_id_set": False,
                    "api_hash_set": False,
                    "session_string_set": False,
                }
            },
        )(),
    )

    body = main.telegram_research_config_view()

    assert body["telegram_research"]["ready"] is False
    assert "telegram_session_string" in body["telegram_research"]["missing_fields"]


def test_source_movers_endpoint_uses_repository(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "list_source_movers",
        lambda limit=10: [
            {
                "account_identifier": "pump.fun",
                "platform": "launchpad",
                "status": "active",
                "projects_24h": 9,
                "qualified_24h": 4,
                "avg_score_24h": 84.2,
                "momentum_score": 31.4,
            }
        ],
    )

    body = main.source_movers(limit=5)

    assert body["items"][0]["account_identifier"] == "pump.fun"
    assert body["items"][0]["momentum_score"] == 31.4


def test_source_templates_endpoint_returns_examples(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "list_source_templates",
        lambda: [
            {"mode": "rss", "label": "RSS feed", "description": "Feed", "example": {"mode": "rss"}},
            {"mode": "sitemap", "label": "Solana homepage crawler", "description": "Crawler", "example": {"mode": "sitemap"}},
            {"mode": "sitemap", "label": "Sitemap crawler", "description": "Crawler", "example": {"mode": "sitemap"}},
        ],
    )

    body = main.source_templates()

    assert body["items"][0]["mode"] == "rss"
    assert body["items"][1]["label"] == "Solana homepage crawler"
    assert body["items"][2]["example"]["mode"] == "sitemap"


def test_export_state_endpoint_uses_service(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "build_export_payload",
        lambda limit=20: {"dashboard": {"summary": {"total_projects": 1}}, "runtime_config": {"daily_alert_limit": 30}},
    )

    body = main.export_state()

    assert body["dashboard"]["summary"]["total_projects"] == 1
    assert body["runtime_config"]["daily_alert_limit"] == 30


def test_export_state_endpoint_reports_error_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "build_export_payload",
        lambda limit=20: {"error": "db unavailable", "dashboard": {"error": "db unavailable"}, "runtime_config": {"daily_alert_limit": 30}},
    )

    body = main.export_state()

    assert body["error"] == "db unavailable"
    assert body["dashboard"]["error"] == "db unavailable"
