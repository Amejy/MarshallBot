# MarshallBot Architecture

## Objective

Discover new Solana and BSC meme coin communities early, score them for quality, and send only the best opportunities to Telegram.

## Design goals

- high reliability
- low operational cost
- simple horizontal scaling
- automatic recovery from failures
- strong deduplication
- configurable ranking

## System overview

### 1. Ingestion

Collectors monitor:

- launchpads
- Telegram public channels and groups
- project websites
- social announcement sources

Each collector emits normalized events into a queue.

### 2. Normalization

The normalizer extracts:

- project name
- chain
- website
- Telegram link
- social links
- source metadata

It also creates a canonical fingerprint for deduplication.

### 3. Enrichment

Enrichment workers:

- fetch websites
- parse HTML and rendered content
- extract links and metadata
- evaluate page quality
- inspect linked social profiles

### 4. Filtering

Reject candidates that:

- lack a website
- lack Telegram
- are obvious spam
- are duplicates
- have no real activity

### 5. Scoring

The ranking engine calculates a 0 to 100 score using:

- freshness
- Telegram quality
- social activity
- website quality
- growth rate
- source quality
- community activity
- spam penalties

Scores are stored historically so the system can be tuned over time.

### 6. Alerting

The alert worker sends only the highest-ranked opportunities to Telegram.

To avoid spam:

- use a daily cap
- use a minimum score threshold
- deduplicate alerts
- prefer the best projects from the last 24 hours

## Data flow

1. Collector sees a new source item.
2. Event is normalized into a candidate project.
3. Candidate is enriched and validated.
4. Candidate is scored.
5. Candidate is compared against the alert threshold.
6. If eligible, a Telegram alert is sent.
7. Delivery result is stored.

## Scaling approach

The first production deployment should use:

- one API container
- one or more worker containers
- Redis for queueing
- PostgreSQL for storage

As traffic grows:

- split collectors, enrichment, scoring, and alerting into separate worker groups
- scale each worker type independently
- keep Postgres managed and backed up
- keep Redis small and close to the workers

## Suggested service boundaries

- `api`: health, admin, and future dashboard endpoints
- `collector-worker`: source ingestion
- `enrichment-worker`: website and social parsing
- `scoring-worker`: ranking engine
- `alert-worker`: Telegram delivery

