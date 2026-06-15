from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    min_score_to_alert: float = 75.0
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


settings = Settings()
