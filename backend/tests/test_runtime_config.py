from __future__ import annotations

from app.core import runtime_config


def test_runtime_config_round_trip(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "runtime.json"
    monkeypatch.setattr(runtime_config, "RUNTIME_CONFIG_PATH", config_path)
    history_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        runtime_config,
        "append_runtime_config_history",
        lambda config, changed_by="dashboard": history_calls.append({"config": config, "changed_by": changed_by}),
    )

    saved = runtime_config.save_runtime_config(
        {
            "daily_alert_limit": 17,
            "min_score_to_alert": 81.5,
            "ranking_weights": {
                "freshness": 0.25,
                "telegram_presence": 0.2,
            },
        }
    )
    loaded = runtime_config.load_runtime_config()

    assert config_path.exists()
    assert saved["daily_alert_limit"] == 17
    assert loaded["daily_alert_limit"] == 17
    assert loaded["min_score_to_alert"] == 81.5
    assert loaded["ranking_weights"]["freshness"] == 0.25
    assert loaded["ranking_weights"]["telegram_presence"] == 0.2
    assert loaded["ranking_weights"]["website_quality"] == runtime_config.DEFAULT_WEIGHTS["website_quality"]
    assert history_calls[0]["changed_by"] == "dashboard"


def test_apply_runtime_config_merges_existing_values(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "runtime.json"
    monkeypatch.setattr(runtime_config, "RUNTIME_CONFIG_PATH", config_path)
    history_calls: list[str] = []
    monkeypatch.setattr(
        runtime_config,
        "append_runtime_config_history",
        lambda config, changed_by="dashboard": history_calls.append(changed_by),
    )

    runtime_config.save_runtime_config(
        {
            "daily_alert_limit": 20,
            "min_score_to_alert": 77,
            "ranking_weights": {"freshness": 0.3, "spam_penalty": 0.05},
        }
    )
    updated = runtime_config.apply_runtime_config(
        {
            "min_score_to_alert": 83,
            "ranking_weights": {"website_quality": 0.22},
        }
    )

    assert updated["daily_alert_limit"] == 20
    assert updated["min_score_to_alert"] == 83.0
    assert updated["ranking_weights"]["freshness"] == 0.3
    assert updated["ranking_weights"]["website_quality"] == 0.22
    assert history_calls[-1] == "dashboard"
