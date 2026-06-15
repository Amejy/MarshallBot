from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


def load_env_file() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized_key = key.strip()
        normalized_value = value.strip()
        os.environ.setdefault(normalized_key, normalized_value)
        os.environ.setdefault(normalized_key.upper(), normalized_value)


def main() -> int:
    load_env_file()
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("telegram_bot_token")
    if not token:
        print("Set telegram_bot_token in .env first.", file=sys.stderr)
        return 1

    updates_url = f"https://api.telegram.org/bot{token}/getUpdates"
    request = Request(updates_url, method="GET")
    try:
        with urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        print(
            "Cannot reach api.telegram.org from this machine.\n"
            "This is a network/DNS issue, not a script issue.\n"
            "Check your internet connection, VPN, DNS, or firewall, then run the script again.\n"
            f"Error: {exc}",
            file=sys.stderr,
        )
        return 1

    if not data.get("ok", False):
        print(json.dumps(data, indent=2))
        print("\nTelegram returned an error. Check that the bot token is correct.")
        return 1

    print(json.dumps(data, indent=2))
    updates = data.get("result", [])
    if not updates:
        webhook_url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
        try:
            with urlopen(Request(webhook_url, method="GET"), timeout=20) as response:
                webhook_data = json.loads(response.read().decode("utf-8"))
        except URLError as exc:
            print(
                "Telegram responded to getUpdates, but webhook info could not be fetched.\n"
                f"Error: {exc}",
                file=sys.stderr,
            )
            return 1

        webhook_info = webhook_data.get("result", {}) if webhook_data.get("ok", False) else {}
        webhook_target = webhook_info.get("url")
        if webhook_target:
            print(
                "\nNo updates yet, and this bot already has a webhook configured.\n"
                f"Webhook URL: {webhook_target}\n"
                "Delete the webhook, then send /start and a message to the bot again."
            )
        else:
            print("\nNo updates yet. Open the bot in Telegram, press Start, and send a message first.")
        return 0

    chat_ids = []
    for update in updates:
        message = update.get("message") or update.get("channel_post") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is not None:
            chat_ids.append(chat_id)

    if chat_ids:
        print("\nChat IDs found:")
        for chat_id in sorted(set(chat_ids)):
            print(chat_id)
    else:
        print("\nNo chat IDs found in the updates.")
        print("If this was a private chat, make sure you sent a message directly to the bot.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
