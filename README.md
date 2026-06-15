# MarshallBot

Crypto community early discovery system for Solana and BSC meme coin opportunities.

## What this repo will become

The system is designed to:

- discover new projects from launchpads, Telegram, websites, and social sources
- enrich each candidate with website and community metadata
- deduplicate aggressively
- score opportunities with configurable weights
- send only the best alerts to Telegram

## Initial architecture

- `FastAPI` API for health checks, admin endpoints, and future control surfaces
- `Celery` workers with `Redis` for source collection, enrichment, scoring, and alerting
- `PostgreSQL` for durable storage and analytics
- `Telethon` for research-layer Telegram monitoring
- `python-telegram-bot` for alert delivery
- `Playwright` for website extraction and rendering

## Repository layout

- `backend/app` - application code
- `backend/app/db/schema.sql` - database schema
- `backend/tests` - unit tests
- `docker-compose.yml` - local stack

## Quick Start

1. Copy `.env.example` to `.env` and fill in your Telegram values.
2. Keep these lists empty for now unless you want to preload custom sources:
   - `launchpad_sources=[]`
   - `telegram_channels=[]`
   - `social_accounts=[]`
   - `admin_chat_ids=[]`
   - If you want to enable the built-in presets from `.env`, set names like `pump-fun`, `four-meme`, or `alpha-meme-watch` in the corresponding list.
3. Start the stack:
   - `make up` starts the backend, worker, beat, Postgres, and Redis without exposing the API on your host
   - `make up-dev` starts the same stack and exposes the API at `http://localhost:8000`
   - `make up-tunnel` starts the same stack plus Cloudflare Tunnel for a public URL
   - `make up-prod` starts the same stack with automatic restarts and exposes the API on `http://localhost:8000`
4. Check status:
   - `make ps`
   - `make ps-tunnel`
   - `make ps-prod`
   - `make logs`
   - `make logs-tunnel`
   - `make logs-prod`
5. Stop everything:
   - `make down`
   - `make clean-tunnel`
   - `make clean-prod`

## Environment Variables

The main values you may need are:

- `database_url` - Postgres connection string used by the API and workers
- `redis_url` - Redis connection string used by Celery
- `telegram_bot_token` - bot token for alert delivery
- `telegram_chat_id` - your private Telegram chat ID for alerts
- `telegram_api_id` and `telegram_api_hash` - only needed for Telegram research-layer login
- `telegram_session_string` - saved Telethon session string after login
- `daily_alert_limit` - max alerts sent per day
- `min_score_to_alert` - minimum score required before an opportunity is alerted

## Local Notes

- The API service is exposed only in the dev compose file, so it will not collide with a local app already using port `8000`.
- Postgres and Redis are kept internal to Docker by default, so they will not take over `5432` or `6379` on your machine.

## Deployment

See [docs/deployment.md](docs/deployment.md) for the exact production command sequence and verification steps.

## Next milestones

1. Build source adapters for launchpads and Telegram channels.
2. Add website extraction and link parsing.
3. Implement scoring and daily alert throttling.
4. Wire the Telegram bot alert layer.
5. Add deployment and recovery automation.
