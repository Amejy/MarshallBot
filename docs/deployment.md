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

## Start with tunnel

```bash
make up-tunnel
```

If you prefer the long form:

```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.tunnel.yml up --build -d
```

## Optional production start

If you only want the local stack without the tunnel:

```bash
make up-prod
```

If your environment does not have the `make` target available, run:

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

## Verify

Check the API:

```bash
curl http://127.0.0.1:8000/health
```

Open the dashboard:

```text
http://127.0.0.1:8000/dashboard
```

## Stop

```bash
make clean-prod
```

## Cloudflare flow

1. Install Docker and Docker Compose on the machine that will run MarshallBot.
2. Copy `.env.example` to `.env`.
3. Fill in the required values:
   - `telegram_bot_token`
   - `telegram_chat_id`
   - `telegram_api_id`
   - `telegram_api_hash`
   - `telegram_session_string`
4. Add any launchpad, Telegram, or social presets you want enabled.
5. Run `make up-tunnel`.
6. Run `make tunnel-url` to print the public Cloudflare URL from the logs.
7. Or run `make tunnel-open` to print the URL and open the dashboard in your browser.
8. Run `make verify-deploy BASE_URL=https://your-tunnel.trycloudflare.com` to smoke-test the public URL.
9. Open the dashboard through that URL at `/dashboard`.

If you want a single command that starts the stack and verifies the tunnel as soon as it appears, run:

```bash
make deploy-tunnel
```

Before you start the deployment, run:

```bash
make release-check
```

That catches missing Telegram credentials or an empty source setup before you waste time on the live stack.

## Notes

- The API will work without Postgres for a limited preview, but the full system needs Postgres and Redis.
- The Telegram bot token should be rotated if it has ever been shared outside your private environment.
