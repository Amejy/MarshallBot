# Telegram Setup

## 1. Bot API alert layer

Create a bot with BotFather in Telegram.

You will get:

- `telegram_bot_token`

You also need the chat ID where the bot should send alerts.

### How to get the chat ID

Common options:

- send a message to the bot, then read `getUpdates`
- use a small helper bot or a temporary script to print the chat ID
- if you want alerts in a private group, add the bot to the group and use that group chat ID

### Fastest way

1. Open `@AlphaMarshall_bot`.
2. Press `Start`.
3. Send any message, like `hello`.
4. Visit:

```text
https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
```

5. Find `chat.id` in the JSON response.

If `getUpdates` is empty, it usually means you have not sent the bot a message yet.

### Local helper script

If you prefer to do it from the repo:

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token_here"
python3 backend/scripts/get_chat_id.py
```

The script prints any chat IDs it finds from recent updates.

## 2. Telegram client research layer

This is optional. You can skip it for now and still continue building the core alert system.

Create an app at `my.telegram.org`.

You will get:

- `telegram_api_id`
- `telegram_api_hash`

If you already have a valid logged-in session string, you can also provide:

- `telegram_session_string`

### Local helper script

If you want the repo to generate the session string for you, set:

```bash
export TELEGRAM_API_ID="your_api_id"
export TELEGRAM_API_HASH="your_api_hash"
python3 backend/scripts/generate_telegram_session.py
```

The script will ask for:

- your phone number
- the login code Telegram sends
- your 2FA password if your account uses one

It prints the `telegram_session_string` at the end.

For safety, the script also writes a backup copy to:

```text
/tmp/marshallbot_telegram_session.txt
```

If the terminal errors after sign-in, you can recover the string from that file.

If Telegram rate-limits the code-login flow, the script now falls back to QR login and writes a helper page to:

```text
/tmp/marshallbot_telegram_qr_login.html
```

Open that page in a browser and scan the QR code with the Telegram app.

## 3. Research channel config

Once you have the API credentials, add channels to `config/sources.json` in this shape:

```json
{
  "name": "my-research-feed",
  "enabled": true,
  "mode": "research",
  "chain": "solana",
  "limit": 100,
  "channels": [
    "mypublicchannel"
  ]
}
```

Notes:

- `channels` can contain public usernames like `mypublicchannel`
- `limit` controls how many recent messages are scanned per channel
- keep the entry `enabled: false` until your Telegram API credentials are added if you want to stage it safely

## 4. What I need from you now

For the core alert path, the only truly blocking items are:

- `telegram_bot_token`
- `telegram_chat_id`

The Telegram API credentials are only needed when you decide to turn on the research layer.
