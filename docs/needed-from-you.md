# Details Needed To Go Live

To connect this system to real sources, I need these details from you:

## Telegram alert layer

- `telegram_bot_token`
- `telegram_chat_id`

## Telegram research layer

Optional for now. We can turn this on later if you want to monitor public channels at scale.

- `telegram_api_id`
- `telegram_api_hash`
- `telegram_session_string` if you want a pre-authorized session
- public Telegram channel usernames or links to monitor first

## Discovery sources

- the launchpads you want monitored first
- the Telegram channels/groups you want monitored first
- any social accounts or keywords you want prioritized
- any sources you explicitly want excluded
- if a launchpad gives us a JSON feed, RSS, or HTML listing URL, send that too

## Source config file

- `config/sources.json` will drive the initial source registry
- if you do not create it, the app falls back to a sample source so you can test the pipeline

## Scoring preferences

- your preferred minimum score for alerts
- whether you want the system to bias more toward freshness or community traction
- any chain preference weighting between Solana and BSC

## Operational preferences

- where you want alerts delivered
- whether you want a daily digest in addition to instant alerts
- whether you want manual review before first-time source activation

## What is blocking now

Only these are needed to keep building the live alert path:

- `telegram_bot_token`
- `telegram_chat_id`

The Telegram API credentials can wait until the research layer is a priority again.

## Nice to have

- examples of projects you considered "good"
- examples of projects you considered "spam"
- any historical watchlist or blacklist
