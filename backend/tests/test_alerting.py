from app import tasks
from app.services.alerting import build_alert_message, within_alert_budget


def test_within_alert_budget() -> None:
    assert within_alert_budget(29, 30) is True
    assert within_alert_budget(30, 30) is False


def test_maybe_alert_stops_when_daily_limit_reached(monkeypatch) -> None:
    monkeypatch.setattr(tasks, "count_alerts_sent_since", lambda hours=24: 30)
    monkeypatch.setattr(tasks, "delivery_ready", lambda token, chat_id: True)

    payload = {
        "canonical_name": "TestCoin",
        "chain": "solana",
        "website_url": "https://example.com",
        "telegram_url": "https://t.me/testcoin",
        "launch_source": "pump.fun",
        "score": 92.0,
    }

    result = tasks.maybe_alert(payload)

    assert result["alert_created"] is True
    assert result["alert_sent"] is False
    assert result["delivery_skipped"] == "daily_limit_reached"


def test_build_alert_message_includes_explanations() -> None:
    message = build_alert_message(
        {
            "canonical_name": "TestCoin",
            "chain": "solana",
            "website_url": "https://example.com",
            "telegram_url": "https://t.me/testcoin",
            "launch_source": "pump.fun",
            "source_trust_level": 88.0,
            "source_trust_movement": 4.5,
            "score_reasons": {"signals": {"source_quality": 90}},
            "score_explanations": ["Telegram link present", "Website looks complete"],
        },
        93.5,
    )

    assert "Why:" in message
    assert "- Telegram link present" in message
    assert "Source Trust: 88.0 (Strong)" in message
    assert "Source Trend: ↗ +4.5 (up)" in message
    assert "Source Quality: 90.0" in message


def test_retry_alert_delivery_blocks_when_retry_limit_reached(monkeypatch) -> None:
    monkeypatch.setattr(tasks.settings, "telegram_bot_token", "token")
    monkeypatch.setattr(tasks.settings, "telegram_chat_id", "123")
    monkeypatch.setattr(
        tasks,
        "get_alert_attempt",
        lambda alert_id: {
            "id": alert_id,
            "delivery_status": "failed",
            "retry_count": 3,
            "next_retry_at": None,
        },
    )

    result = tasks.retry_alert_delivery(9)

    assert result["ok"] is False
    assert result["reason"] == "retry_limit_reached"


def test_retry_alert_delivery_blocks_until_backoff_expires(monkeypatch) -> None:
    from datetime import datetime, timedelta, timezone

    monkeypatch.setattr(tasks.settings, "telegram_bot_token", "token")
    monkeypatch.setattr(tasks.settings, "telegram_chat_id", "123")
    monkeypatch.setattr(
        tasks,
        "get_alert_attempt",
        lambda alert_id: {
            "id": alert_id,
            "delivery_status": "failed",
            "retry_count": 1,
            "next_retry_at": datetime.now(timezone.utc) + timedelta(minutes=10),
        },
    )

    result = tasks.retry_alert_delivery(9)

    assert result["ok"] is False
    assert result["reason"] == "retry_backoff_active"


def test_retry_due_alerts_retries_due_items(monkeypatch) -> None:
    due_alerts = [{"id": 11}, {"id": 12}]
    retried: list[int] = []

    monkeypatch.setattr(tasks, "list_due_alert_retries", lambda limit=50: due_alerts)
    monkeypatch.setattr(
        tasks,
        "retry_alert_delivery",
        lambda alert_id: retried.append(alert_id) or {"ok": True, "alert_id": alert_id},
    )

    result = tasks.retry_due_alerts(limit=10)

    assert retried == [11, 12]
    assert result["due_count"] == 2
    assert result["retried_count"] == 2
    assert result["blocked_count"] == 0


def test_run_discovery_cycle_attempts_alerts_for_selected_items(monkeypatch) -> None:
    monkeypatch.setattr(tasks, "maybe_alert", lambda payload: {"alert_sent": True, "payload": payload})
    monkeypatch.setattr(
        tasks,
        "process_source",
        lambda source, ranking, source_config=None, enrich_websites=False, score_cooldown_minutes=30: [
            {"canonical_name": "Alpha", "score": 91, "keep": True, "selected": True},
            {"canonical_name": "Beta", "score": 40, "keep": False, "selected": False},
        ],
    )
    monkeypatch.setattr(tasks, "build_default_registry", lambda source_config: type("Registry", (), {"names": lambda self: ["sample"], "get": lambda self, name: object()})())
    monkeypatch.setattr(tasks, "SourceConfig", type("SourceConfig", (), {"load": classmethod(lambda cls: object())}))

    result = tasks.run_discovery_cycle()

    assert result["sample"]["count"] == 2
    assert result["sample"]["kept"] == 1
    assert result["sample"]["selected"] == 1
    assert result["sample"]["alert_attempts"] == 1
    assert result["sample"]["alert_sent"] == 1
