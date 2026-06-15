from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.db.connection import get_connection
from app.services.ranking import DEFAULT_WEIGHTS

RUNTIME_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "runtime.json"


def _base_config() -> dict[str, object]:
    return {
        "daily_alert_limit": settings.daily_alert_limit,
        "min_score_to_alert": settings.min_score_to_alert,
        "ranking_weights": dict(DEFAULT_WEIGHTS | dict(settings.ranking_weights)),
    }


def _normalize_weights(weights: dict[str, object] | None) -> dict[str, float]:
    normalized = dict(DEFAULT_WEIGHTS)
    if not weights:
        return normalized
    for key in DEFAULT_WEIGHTS:
        if key in weights:
            try:
                normalized[key] = float(weights[key])
            except (TypeError, ValueError):
                continue
    return normalized


def load_runtime_config() -> dict[str, object]:
    config = _base_config()
    if not RUNTIME_CONFIG_PATH.exists():
        return config

    try:
        raw = json.loads(RUNTIME_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return config

    if isinstance(raw, dict):
        if "daily_alert_limit" in raw:
            try:
                config["daily_alert_limit"] = int(raw["daily_alert_limit"])
            except (TypeError, ValueError):
                pass
        if "min_score_to_alert" in raw:
            try:
                config["min_score_to_alert"] = float(raw["min_score_to_alert"])
            except (TypeError, ValueError):
                pass
        if isinstance(raw.get("ranking_weights"), dict):
            config["ranking_weights"] = _normalize_weights(raw.get("ranking_weights"))
    return config


def save_runtime_config(config: dict[str, object]) -> dict[str, object]:
    payload = {
        "daily_alert_limit": int(config.get("daily_alert_limit", settings.daily_alert_limit)),
        "min_score_to_alert": float(config.get("min_score_to_alert", settings.min_score_to_alert)),
        "ranking_weights": _normalize_weights(dict(config.get("ranking_weights", {}))),
    }
    RUNTIME_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_CONFIG_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        append_runtime_config_history(payload, changed_by=str(config.get("updated_by", "dashboard")))
    except Exception:
        pass
    return payload


def apply_runtime_config(overrides: dict[str, object]) -> dict[str, object]:
    current = load_runtime_config()
    merged = {
        "daily_alert_limit": overrides.get("daily_alert_limit", current["daily_alert_limit"]),
        "min_score_to_alert": overrides.get("min_score_to_alert", current["min_score_to_alert"]),
        "ranking_weights": dict(current["ranking_weights"]),
    }
    if isinstance(overrides.get("ranking_weights"), dict):
        merged["ranking_weights"] = _normalize_weights(
            {**dict(current["ranking_weights"]), **dict(overrides.get("ranking_weights", {}))}
        )
    if "updated_by" in overrides:
        merged["updated_by"] = overrides["updated_by"]
    return save_runtime_config(merged)


def append_runtime_config_history(config: dict[str, object], changed_by: str = "dashboard") -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO runtime_config_history (
                    changed_by,
                    daily_alert_limit,
                    min_score_to_alert,
                    ranking_weights
                )
                VALUES (%s, %s, %s, %s::jsonb)
                """,
                (
                    changed_by,
                    int(config.get("daily_alert_limit", settings.daily_alert_limit)),
                    float(config.get("min_score_to_alert", settings.min_score_to_alert)),
                    json.dumps(_normalize_weights(dict(config.get("ranking_weights", {})))),
                ),
            )


def list_runtime_config_history(limit: int = 20) -> list[dict]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        changed_at,
                        changed_by,
                        daily_alert_limit,
                        min_score_to_alert,
                        ranking_weights
                    FROM runtime_config_history
                    ORDER BY changed_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                return list(cur.fetchall())
    except Exception:
        return []
