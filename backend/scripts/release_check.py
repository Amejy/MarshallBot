from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.core.source_config import SourceConfig


def _missing_env_values() -> list[str]:
    missing: list[str] = []
    if not settings.telegram_bot_token:
        missing.append("telegram_bot_token")
    if not settings.telegram_chat_id:
        missing.append("telegram_chat_id")
    if not settings.telegram_api_id:
        missing.append("telegram_api_id")
    if not settings.telegram_api_hash:
        missing.append("telegram_api_hash")
    return missing


def _source_summary() -> dict[str, int]:
    source_config = SourceConfig.load()
    return {
        "launchpads": len(source_config.launchpads),
        "telegram_channels": len(source_config.telegram_channels),
        "social_accounts": len(source_config.social_accounts),
    }


def main() -> int:
    print("MarshallBot release check")
    print(f"Environment: {settings.environment}")
    print(f"Docker compose file root: {Path.cwd()}")

    missing = _missing_env_values()
    if missing:
        print("Missing required environment values:")
        for name in missing:
            print(f"- {name}")
    else:
        print("Required Telegram environment values: OK")

    source_summary = _source_summary()
    active_sources = sum(source_summary.values())
    print(
        "Configured sources: "
        f"{source_summary['launchpads']} launchpads, "
        f"{source_summary['telegram_channels']} telegram channels, "
        f"{source_summary['social_accounts']} social accounts"
    )

    if active_sources == 0:
        print("No sources are configured. Enable at least one launchpad, Telegram channel, or social account.")
    else:
        print("At least one source is configured: OK")

    if missing or active_sources == 0:
        return 1

    print("Release check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
