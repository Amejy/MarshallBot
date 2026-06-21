from __future__ import annotations

import json
from typing import get_origin

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources.providers.dotenv import DotEnvSettingsSource
from pydantic_settings.sources.providers.env import EnvSettingsSource


def _parse_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, (tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        if raw.startswith("[") and raw.endswith("]"):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        return [item.strip().strip('"').strip("'") for item in raw.split(",") if item.strip().strip('"').strip("'")]
    return [str(value).strip()]


def _is_list_field(field: object) -> bool:
    annotation = getattr(field, "annotation", None)
    origin = get_origin(annotation)
    return origin in {list, tuple, set}


class _CSVFriendlySettingsSourceMixin:
    def prepare_field_value(self, field_name, field, value, value_is_complex):  # type: ignore[override]
        if _is_list_field(field) and isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("[") and raw.endswith("]"):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            return _parse_list(raw)
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class CSVFriendlyEnvSettingsSource(_CSVFriendlySettingsSourceMixin, EnvSettingsSource):
    pass


class CSVFriendlyDotEnvSettingsSource(_CSVFriendlySettingsSourceMixin, DotEnvSettingsSource):
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+psycopg://marshallbot:marshallbot@postgres:5432/marshallbot"
    redis_url: str = "redis://redis:6379/0"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_api_id: int = 0
    telegram_api_hash: str = ""
    telegram_session_string: str = ""
    daily_alert_limit: int = 30
    min_score_to_alert: float = 78.0
    max_project_age_hours: float = 24.0
    max_pair_age_hours: float = 24.0
    launchpad_sources: list[str] = []
    telegram_channels: list[str] = []
    social_accounts: list[str] = []
    admin_chat_ids: list[str] = []
    ranking_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "freshness": 0.20,
            "telegram_presence": 0.15,
            "social_activity": 0.15,
            "website_quality": 0.15,
            "growth_rate": 0.15,
            "source_quality": 0.10,
            "community_activity": 0.10,
            "spam_penalty": 0.10,
        }
    )

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        return (
            init_settings,
            CSVFriendlyEnvSettingsSource(settings_cls),
            CSVFriendlyDotEnvSettingsSource(settings_cls),
            file_secret_settings,
        )


settings = Settings()
