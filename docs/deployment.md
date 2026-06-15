# Deployment

## Recommended production stack

Use Docker Compose with:

- `api`
- `worker`
- `beat`
- `postgres`
- `redis`

The production override exposes the API on port `8000` and keeps the services restarting automatically.

## Render deployment

The repository includes a Render blueprint at [`render.yaml`](/home/mohammed/MarshallBot/render.yaml).

### What it covers

- API web service
- Celery worker
- Celery beat
- schema bootstrap before deploy

### What you still need to add in Render

- PostgreSQL connection string
- Redis connection string
- Telegram bot credentials
- Telegram alert chat ID

The blueprint leaves those as unset so Render will prompt you during setup.

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

## Production start

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

## Render flow

1. Create a new Render Blueprint from this repository.
2. Import `render.yaml`.
3. Paste your `DATABASE_URL`, `REDIS_URL`, and Telegram secrets when Render prompts you.
4. Deploy the services.
5. Open `/health` and `/dashboard` on the deployed API.

## Notes

- The API will work without Postgres for a limited preview, but the full system needs Postgres and Redis.
- The Telegram bot token should be rotated if it has ever been shared outside your private environment.
