from __future__ import annotations

import httpx

from app.core.config import settings


class TelegramBotClient:
    def __init__(self, token: str | None = None) -> None:
        self.token = token or settings.telegram_bot_token

    async def send_message(self, chat_id: str, text: str) -> dict:
        if not self.token:
            raise RuntimeError("telegram_bot_token is not configured")

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": False,
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

