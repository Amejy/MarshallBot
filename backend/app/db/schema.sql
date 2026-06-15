CREATE TABLE IF NOT EXISTS projects (
  id BIGSERIAL PRIMARY KEY,
  canonical_name TEXT NOT NULL,
  normalized_name TEXT NOT NULL,
  chain TEXT NOT NULL CHECK (chain IN ('solana', 'bsc')),
  website_url TEXT,
  website_domain TEXT,
  telegram_url TEXT,
  x_url TEXT,
  discord_url TEXT,
  launch_source TEXT NOT NULL,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status TEXT NOT NULL DEFAULT 'new',
  best_score NUMERIC(5,2),
  current_score NUMERIC(5,2),
  duplicate_of_project_id BIGINT REFERENCES projects(id) ON DELETE SET NULL,
  risk_flags JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (normalized_name, chain)
);

CREATE INDEX IF NOT EXISTS idx_projects_status_score ON projects (status, current_score DESC);
CREATE INDEX IF NOT EXISTS idx_projects_first_seen ON projects (first_seen_at DESC);

CREATE TABLE IF NOT EXISTS project_events (
  id BIGSERIAL PRIMARY KEY,
  project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
  source_type TEXT NOT NULL,
  source_name TEXT NOT NULL,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  observed_at TIMESTAMPTZ NOT NULL,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS website_snapshots (
  id BIGSERIAL PRIMARY KEY,
  project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  url TEXT NOT NULL,
  title TEXT,
  meta_description TEXT,
  html_hash TEXT NOT NULL,
  text_hash TEXT NOT NULL,
  screenshot_path TEXT,
  parsed_data JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_website_snapshots_hash ON website_snapshots (project_id, html_hash, text_hash);

CREATE TABLE IF NOT EXISTS social_profiles (
  id BIGSERIAL PRIMARY KEY,
  project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
  platform TEXT NOT NULL,
  url TEXT NOT NULL,
  handle TEXT,
  follower_count INTEGER,
  post_count INTEGER,
  engagement_score NUMERIC(5,2),
  created_at_estimate TIMESTAMPTZ,
  last_checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  profile_data JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_social_profiles_unique ON social_profiles (project_id, platform, url);

CREATE TABLE IF NOT EXISTS scores (
  id BIGSERIAL PRIMARY KEY,
  project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
  scored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  model_version TEXT NOT NULL,
  freshness_score NUMERIC(5,2) NOT NULL,
  telegram_score NUMERIC(5,2) NOT NULL,
  social_score NUMERIC(5,2) NOT NULL,
  website_score NUMERIC(5,2) NOT NULL,
  growth_score NUMERIC(5,2) NOT NULL,
  source_quality_score NUMERIC(5,2) NOT NULL,
  community_score NUMERIC(5,2) NOT NULL,
  spam_penalty NUMERIC(5,2) NOT NULL,
  final_score NUMERIC(5,2) NOT NULL,
  score_reasons JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_scores_project_scored_at ON scores (project_id, scored_at DESC);
CREATE INDEX IF NOT EXISTS idx_scores_final_score ON scores (final_score DESC);

CREATE TABLE IF NOT EXISTS alerts_sent (
  id BIGSERIAL PRIMARY KEY,
  project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
  sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  chat_id TEXT NOT NULL,
  message_id TEXT,
  dedupe_key TEXT NOT NULL UNIQUE,
  score_at_send NUMERIC(5,2) NOT NULL,
  delivery_status TEXT NOT NULL DEFAULT 'sent',
  retry_count INTEGER NOT NULL DEFAULT 0,
  next_retry_at TIMESTAMPTZ,
  last_error TEXT
);

CREATE TABLE IF NOT EXISTS dedupe_fingerprints (
  id BIGSERIAL PRIMARY KEY,
  fingerprint_type TEXT NOT NULL,
  fingerprint_value TEXT NOT NULL,
  project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (fingerprint_type, fingerprint_value)
);

CREATE TABLE IF NOT EXISTS source_accounts (
  id BIGSERIAL PRIMARY KEY,
  platform TEXT NOT NULL,
  account_identifier TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'active',
  trust_level NUMERIC(5,2) NOT NULL DEFAULT 0,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS runtime_config_history (
  id BIGSERIAL PRIMARY KEY,
  changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  changed_by TEXT NOT NULL DEFAULT 'dashboard',
  daily_alert_limit INTEGER NOT NULL,
  min_score_to_alert NUMERIC(5,2) NOT NULL,
  ranking_weights JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_runtime_config_history_changed_at ON runtime_config_history (changed_at DESC);

CREATE TABLE IF NOT EXISTS source_account_history (
  id BIGSERIAL PRIMARY KEY,
  source_account_id BIGINT REFERENCES source_accounts(id) ON DELETE CASCADE,
  changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  changed_by TEXT NOT NULL DEFAULT 'dashboard',
  action TEXT NOT NULL,
  status_before TEXT,
  status_after TEXT,
  trust_before NUMERIC(5,2),
  trust_after NUMERIC(5,2),
  note TEXT
);

CREATE INDEX IF NOT EXISTS idx_source_account_history_account_changed_at ON source_account_history (source_account_id, changed_at DESC);
