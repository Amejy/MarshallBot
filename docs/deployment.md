# Deployment

## Recommended deployment stack

Use Docker Compose with:

- `api`
- `worker`
- `beat`
- `postgres`
- `redis`
- `cloudflared`

The tunnel override keeps everything local and exposes the API through a Cloudflare Tunnel URL.

## Prerequisites

1. Install Docker and Docker Compose.
2. Copy `.env.example` to `.env`.
3. Fill in the required values:
   - `telegram_bot_token`
   - `telegram_chat_id`
   - `telegram_api_id`
   - `telegram_api_hash`
   - `telegram_session_string`
4. Add any launchpad, Telegram, or social presets you want enabled.

## Cloudflare flow

1. Run `make go-live`.
2. Open the dashboard through the tunnel URL at `/dashboard`.
3. If you need the manual fallback, use:
   - `make release-check`
   - `make deploy-tunnel`
   - `make tunnel-url`
   - `make tunnel-open`
   - `make verify-deploy BASE_URL=https://your-tunnel.trycloudflare.com`

`make go-live` is the default path. It runs the release check first, then starts the tunnel deployment.

The manual fallback is there if you want to split the steps or inspect the logs yourself.

## Notes

- The API will work without Postgres for a limited preview, but the full system needs Postgres and Redis.
- The Telegram bot token should be rotated if it has ever been shared outside your private environment.
