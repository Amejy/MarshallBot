from __future__ import annotations

from datetime import datetime, timezone

from app.core.dedupe import fingerprint, normalize_contact_identifier, normalize_domain, normalize_name
from app.db.connection import get_connection

ALERT_RETRY_LIMIT = 3
ALERT_RETRY_BASE_MINUTES = 15


def _backoff_minutes(retry_count: int) -> int:
    if retry_count <= 0:
        return ALERT_RETRY_BASE_MINUTES
    return min(ALERT_RETRY_BASE_MINUTES * (2 ** (retry_count - 1)), 6 * 60)


def upsert_project(project: dict) -> dict:
    normalized_name = project.get("normalized_name") or normalize_name(project["canonical_name"])
    website_url = project.get("website_url")
    website_domain = normalize_domain(website_url) if website_url else None
    telegram_identifier = normalize_contact_identifier(project.get("telegram_url"))
    x_identifier = normalize_contact_identifier(project.get("x_url"))
    discord_identifier = normalize_contact_identifier(project.get("discord_url"))

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO projects (
                    canonical_name, normalized_name, chain, website_url, website_domain,
                    telegram_url, x_url, discord_url, launch_source, first_seen_at, last_seen_at, status
                )
                VALUES (
                    %(canonical_name)s, %(normalized_name)s, %(chain)s, %(website_url)s, %(website_domain)s,
                    %(telegram_url)s, %(x_url)s, %(discord_url)s, %(launch_source)s, %(first_seen_at)s, %(last_seen_at)s, %(status)s
                )
                ON CONFLICT (normalized_name, chain) DO UPDATE SET
                    canonical_name = EXCLUDED.canonical_name,
                    website_url = COALESCE(EXCLUDED.website_url, projects.website_url),
                    website_domain = COALESCE(EXCLUDED.website_domain, projects.website_domain),
                    telegram_url = COALESCE(EXCLUDED.telegram_url, projects.telegram_url),
                    x_url = COALESCE(EXCLUDED.x_url, projects.x_url),
                    discord_url = COALESCE(EXCLUDED.discord_url, projects.discord_url),
                    launch_source = EXCLUDED.launch_source,
                    last_seen_at = EXCLUDED.last_seen_at
                RETURNING *;
                """,
                {
                    "canonical_name": project["canonical_name"],
                    "normalized_name": normalized_name,
                    "chain": project["chain"],
                    "website_url": website_url,
                    "website_domain": website_domain,
                    "telegram_url": project.get("telegram_url"),
                    "x_url": project.get("x_url"),
                    "discord_url": project.get("discord_url"),
                    "launch_source": project.get("launch_source", "unknown"),
                    "first_seen_at": project.get("first_seen_at", datetime.now(timezone.utc)),
                    "last_seen_at": datetime.now(timezone.utc),
                    "status": project.get("status", "new"),
                },
            )
            row = cur.fetchone()
            if row and website_domain:
                cur.execute(
                    """
                    SELECT id
                    FROM projects
                    WHERE website_domain = %s
                      AND id <> %s
                    ORDER BY first_seen_at ASC
                    LIMIT 1
                    """,
                    (website_domain, row["id"]),
                )
                duplicate = cur.fetchone()
                if duplicate:
                    cur.execute(
                        """
                        UPDATE projects
                        SET status = 'duplicate',
                            duplicate_of_project_id = %s,
                            last_seen_at = NOW()
                        WHERE id = %s
                        RETURNING *
                        """,
                        (duplicate["id"], row["id"]),
                    )
                    row = cur.fetchone()
            if row:
                dedupe_fingerprints = [
                    ("project", project_fingerprint(row)),
                    ("website_domain", website_domain),
                    ("telegram_url", telegram_identifier),
                    ("x_url", x_identifier),
                    ("discord_url", discord_identifier),
                ]
                for fingerprint_type, fingerprint_value in dedupe_fingerprints:
                    if fingerprint_value:
                        cur.execute(
                            """
                            INSERT INTO dedupe_fingerprints (
                                fingerprint_type, fingerprint_value, project_id, first_seen_at, last_seen_at
                            )
                            VALUES (%s, %s, %s, NOW(), NOW())
                            ON CONFLICT (fingerprint_type, fingerprint_value) DO UPDATE SET
                                project_id = EXCLUDED.project_id,
                                last_seen_at = NOW()
                            """,
                            (fingerprint_type, fingerprint_value, row["id"]),
                        )
    return row or {}


def insert_project_event(project_id: int, source_type: str, source_name: str, raw_payload: dict) -> None:
    observed_at = raw_payload.get("observed_at") or datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO project_events (project_id, source_type, source_name, raw_payload, observed_at)
                VALUES (%s, %s, %s, %s::jsonb, %s)
                """,
                (project_id, source_type, source_name, raw_payload, observed_at),
            )


def store_website_snapshot(project_id: int, snapshot: dict) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO website_snapshots (
                    project_id, url, title, meta_description, html_hash, text_hash, screenshot_path, parsed_data
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (project_id, html_hash, text_hash) DO NOTHING
                """,
                (
                    project_id,
                    snapshot.get("url"),
                    snapshot.get("title"),
                    snapshot.get("meta_description"),
                    snapshot.get("html_hash"),
                    snapshot.get("text_hash"),
                    snapshot.get("screenshot_path"),
                    snapshot.get("parsed_data", {}),
                ),
            )


def upsert_social_profile(
    project_id: int,
    platform: str,
    url: str,
    handle: str | None = None,
    follower_count: int | None = None,
    post_count: int | None = None,
    engagement_score: float | None = None,
    created_at_estimate=None,
    profile_data: dict | None = None,
) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO social_profiles (
                    project_id, platform, url, handle, follower_count, post_count,
                    engagement_score, created_at_estimate, last_checked_at, profile_data
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s::jsonb)
                ON CONFLICT (project_id, platform, url) DO UPDATE SET
                    handle = COALESCE(EXCLUDED.handle, social_profiles.handle),
                    follower_count = COALESCE(EXCLUDED.follower_count, social_profiles.follower_count),
                    post_count = COALESCE(EXCLUDED.post_count, social_profiles.post_count),
                    engagement_score = COALESCE(EXCLUDED.engagement_score, social_profiles.engagement_score),
                    created_at_estimate = COALESCE(EXCLUDED.created_at_estimate, social_profiles.created_at_estimate),
                    last_checked_at = NOW(),
                    profile_data = social_profiles.profile_data || EXCLUDED.profile_data
                RETURNING *;
                """,
                (
                    project_id,
                    platform,
                    url,
                    handle,
                    follower_count,
                    post_count,
                    engagement_score,
                    created_at_estimate,
                    profile_data or {},
                ),
            )
            return cur.fetchone()


def record_dedupe_fingerprint(fingerprint_type: str, fingerprint_value: str, project_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO dedupe_fingerprints (
                    fingerprint_type, fingerprint_value, project_id, first_seen_at, last_seen_at
                )
                VALUES (%s, %s, %s, NOW(), NOW())
                ON CONFLICT (fingerprint_type, fingerprint_value) DO UPDATE SET
                    project_id = EXCLUDED.project_id,
                    last_seen_at = NOW()
                """,
                (fingerprint_type, fingerprint_value, project_id),
            )


def upsert_source_account(platform: str, account_identifier: str, trust_level: float = 0.0, metadata: dict | None = None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO source_accounts (
                    platform, account_identifier, trust_level, first_seen_at, last_seen_at, metadata
                )
                VALUES (%s, %s, %s, NOW(), NOW(), %s::jsonb)
                ON CONFLICT (account_identifier) DO UPDATE SET
                    platform = EXCLUDED.platform,
                    trust_level = GREATEST(source_accounts.trust_level, EXCLUDED.trust_level),
                    last_seen_at = NOW(),
                    metadata = source_accounts.metadata || EXCLUDED.metadata
                """,
                (platform, account_identifier, trust_level, metadata or {}),
            )
            cur.execute(
                """
                SELECT *
                FROM source_accounts
                WHERE account_identifier = %s
                """,
                (account_identifier,),
            )
            return cur.fetchone()


def _append_source_account_history(
    source_account_id: int,
    action: str,
    status_before: str | None,
    status_after: str | None,
    trust_before: float | None,
    trust_after: float | None,
    note: str | None = None,
    changed_by: str = "dashboard",
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO source_account_history (
                    source_account_id,
                    changed_by,
                    action,
                    status_before,
                    status_after,
                    trust_before,
                    trust_after,
                    note
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    source_account_id,
                    changed_by,
                    action,
                    status_before,
                    status_after,
                    trust_before,
                    trust_after,
                    note,
                ),
            )


def list_source_accounts(limit: int = 100) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM source_accounts
                ORDER BY status ASC, trust_level DESC, last_seen_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return list(cur.fetchall())


def get_alert_attempt(alert_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    a.id,
                    a.project_id,
                    a.sent_at,
                    a.chat_id,
                    a.message_id,
                    a.dedupe_key,
                    a.score_at_send,
                    a.delivery_status,
                    a.retry_count,
                    a.next_retry_at,
                    a.last_error,
                    p.canonical_name,
                    p.chain,
                    p.website_url,
                    p.telegram_url,
                    p.x_url,
                    p.discord_url,
                    p.launch_source,
                    s.score_reasons,
                    s.model_version,
                    s.scored_at
                FROM alerts_sent a
                LEFT JOIN projects p ON p.id = a.project_id
                LEFT JOIN LATERAL (
                    SELECT score_reasons, model_version, scored_at
                    FROM scores
                    WHERE project_id = a.project_id
                    ORDER BY scored_at DESC
                    LIMIT 1
                ) s ON TRUE
                WHERE a.id = %s
                """,
                (alert_id,),
            )
            return cur.fetchone()


def set_source_trust(account_identifier: str, trust_level: float) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, status, trust_level FROM source_accounts WHERE account_identifier = %s",
                (account_identifier,),
            )
            existing = cur.fetchone() or {}
            cur.execute(
                """
                UPDATE source_accounts
                SET trust_level = %s,
                    last_seen_at = NOW()
                WHERE account_identifier = %s
                """,
                (trust_level, account_identifier),
            )
            if existing.get("id") is not None:
                try:
                    _append_source_account_history(
                        int(existing["id"]),
                        "trust_updated",
                        str(existing.get("status")) if existing.get("status") is not None else None,
                        str(existing.get("status")) if existing.get("status") is not None else None,
                        float(existing.get("trust_level", 0) or 0),
                        float(trust_level),
                    )
                except Exception:
                    pass


def _next_source_trust(current_trust: float, score: float, qualified: bool, spammy: bool = False) -> float:
    current_trust = max(0.0, min(100.0, float(current_trust)))
    score = max(0.0, min(100.0, float(score)))
    if qualified:
        delta = 1.5 + (score / 100.0) * 5.0
        if score >= 90:
            delta += 2.5
        return min(100.0, current_trust + delta)

    delta = 1.5 + max(0.0, (75.0 - score) / 20.0)
    if spammy:
        delta += 3.0
    if score <= 25:
        delta += 2.0
    return max(5.0, current_trust - delta)


def adjust_source_trust(
    account_identifier: str,
    score: float,
    qualified: bool,
    spammy: bool = False,
    note: str | None = None,
) -> float | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, status, trust_level FROM source_accounts WHERE account_identifier = %s",
                (account_identifier,),
            )
            existing = cur.fetchone() or {}
            if existing.get("id") is None:
                return None

            current_trust = float(existing.get("trust_level", 0) or 0)
            updated_trust = _next_source_trust(current_trust, score, qualified, spammy=spammy)
            cur.execute(
                """
                UPDATE source_accounts
                SET trust_level = %s,
                    last_seen_at = NOW()
                WHERE account_identifier = %s
                """,
                (updated_trust, account_identifier),
            )
            try:
                _append_source_account_history(
                    int(existing["id"]),
                    "trust_adjusted",
                    str(existing.get("status")) if existing.get("status") is not None else None,
                    str(existing.get("status")) if existing.get("status") is not None else None,
                    current_trust,
                    updated_trust,
                    note=note,
                )
            except Exception:
                pass
            return updated_trust


def set_source_status(account_identifier: str, status: str, trust_level: float | None = None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, status, trust_level FROM source_accounts WHERE account_identifier = %s",
                (account_identifier,),
            )
            existing = cur.fetchone() or {}
            if trust_level is None:
                cur.execute(
                    """
                    UPDATE source_accounts
                    SET status = %s,
                        last_seen_at = NOW()
                    WHERE account_identifier = %s
                    """,
                    (status, account_identifier),
                )
            else:
                cur.execute(
                    """
                    UPDATE source_accounts
                    SET status = %s,
                        trust_level = %s,
                        last_seen_at = NOW()
                    WHERE account_identifier = %s
                    """,
                    (status, trust_level, account_identifier),
                )
            if existing.get("id") is not None:
                try:
                    _append_source_account_history(
                        int(existing["id"]),
                        "status_updated",
                        str(existing.get("status")) if existing.get("status") is not None else None,
                        status,
                        float(existing.get("trust_level", 0) or 0),
                        float(trust_level) if trust_level is not None else float(existing.get("trust_level", 0) or 0),
                    )
                except Exception:
                    pass


def list_source_account_history(account_identifier: str, limit: int = 20) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    h.id,
                    h.changed_at,
                    h.changed_by,
                    h.action,
                    h.status_before,
                    h.status_after,
                    h.trust_before,
                    h.trust_after,
                    h.note
                FROM source_account_history h
                INNER JOIN source_accounts s ON s.id = h.source_account_id
                WHERE s.account_identifier = %s
                ORDER BY h.changed_at DESC
                LIMIT %s
                """,
                (account_identifier, limit),
            )
            return list(cur.fetchall())


def get_source_account(account_identifier: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM source_accounts
                WHERE account_identifier = %s
                """,
                (account_identifier,),
            )
            return cur.fetchone()


def project_fingerprint(project: dict) -> str:
    return fingerprint(
        project.get("canonical_name", ""),
        normalize_domain(project.get("website_url")) if project.get("website_url") else "",
        normalize_contact_identifier(project.get("telegram_url")) or "",
        normalize_contact_identifier(project.get("x_url")) or "",
        normalize_contact_identifier(project.get("discord_url")) or "",
    )


def register_alert_attempt(
    project_id: int | None,
    chat_id: str,
    score: float,
    dedupe_key: str,
    delivery_status: str = "pending",
) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT delivery_status, retry_count FROM alerts_sent WHERE dedupe_key = %s",
                (dedupe_key,),
            )
            existing = cur.fetchone()
            if existing and existing["delivery_status"] == "sent":
                return False

            if existing:
                cur.execute(
                    """
                    UPDATE alerts_sent
                    SET project_id = COALESCE(%s, project_id),
                        chat_id = %s,
                        score_at_send = %s,
                        delivery_status = %s,
                        next_retry_at = CASE WHEN %s = 'pending' THEN next_retry_at ELSE NULL END
                    WHERE dedupe_key = %s
                    """,
                    (project_id, chat_id, score, delivery_status, delivery_status, dedupe_key),
                )
                return True

            cur.execute(
                """
                INSERT INTO alerts_sent (project_id, chat_id, dedupe_key, score_at_send, delivery_status)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (dedupe_key) DO NOTHING
                RETURNING id
                """,
                (project_id, chat_id, dedupe_key, score, delivery_status),
            )
            return cur.fetchone() is not None


def mark_alert_sent(dedupe_key: str, message_id: str | None = None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE alerts_sent
                SET delivery_status = 'sent',
                    message_id = COALESCE(%s, message_id),
                    last_error = NULL,
                    next_retry_at = NULL
                WHERE dedupe_key = %s
                """,
                (message_id, dedupe_key),
            )


def mark_alert_failed(dedupe_key: str, message: str | None = None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT retry_count FROM alerts_sent WHERE dedupe_key = %s",
                (dedupe_key,),
            )
            row = cur.fetchone() or {}
            next_retry_count = int(row.get("retry_count", 0) or 0) + 1
            next_delay_minutes = _backoff_minutes(next_retry_count)
            cur.execute(
                """
                UPDATE alerts_sent
                SET delivery_status = 'failed',
                    retry_count = retry_count + 1,
                    next_retry_at = NOW() + (%s * INTERVAL '1 minute'),
                    last_error = %s,
                    message_id = COALESCE(message_id, %s)
                WHERE dedupe_key = %s
                """,
                (next_delay_minutes, message, message, dedupe_key),
            )


def can_retry_alert(alert: dict) -> tuple[bool, str | None]:
    retry_count = int(alert.get("retry_count", 0) or 0)
    if retry_count >= ALERT_RETRY_LIMIT:
        return False, "retry_limit_reached"

    next_retry_at = alert.get("next_retry_at")
    if next_retry_at and next_retry_at > datetime.now(timezone.utc):
        return False, "retry_backoff_active"
    return True, None


def retry_backoff_minutes(retry_count: int) -> int:
    return _backoff_minutes(retry_count)


def list_due_alert_retries(limit: int = 50) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    a.id,
                    a.project_id,
                    a.sent_at,
                    a.chat_id,
                    a.message_id,
                    a.dedupe_key,
                    a.score_at_send,
                    a.delivery_status,
                    a.retry_count,
                    a.next_retry_at,
                    a.last_error,
                    p.canonical_name,
                    p.chain,
                    p.website_url,
                    p.telegram_url,
                    p.x_url,
                    p.discord_url,
                    p.launch_source,
                    s.score_reasons,
                    s.model_version,
                    s.scored_at
                FROM alerts_sent a
                LEFT JOIN projects p ON p.id = a.project_id
                LEFT JOIN LATERAL (
                    SELECT score_reasons, model_version, scored_at
                    FROM scores
                    WHERE project_id = a.project_id
                    ORDER BY scored_at DESC
                    LIMIT 1
                ) s ON TRUE
                WHERE a.delivery_status IN ('pending', 'failed')
                  AND a.next_retry_at IS NOT NULL
                  AND a.next_retry_at <= NOW()
                ORDER BY a.next_retry_at ASC, a.sent_at ASC
                LIMIT %s
                """,
                (limit,),
            )
            return list(cur.fetchall())


def count_alerts_sent_since(hours: int = 24) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS alert_count
                FROM alerts_sent
                WHERE sent_at >= NOW() - (%s * INTERVAL '1 hour')
                """,
                (hours,),
            )
            row = cur.fetchone() or {}
            return int(row.get("alert_count", 0) or 0)


def persist_score(
    project_id: int,
    model_version: str,
    breakdown: dict,
    final_score: float,
    score_reasons: dict,
    project_status: str | None = None,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO scores (
                    project_id,
                    model_version,
                    freshness_score,
                    telegram_score,
                    social_score,
                    website_score,
                    growth_score,
                    source_quality_score,
                    community_score,
                    spam_penalty,
                    final_score,
                    score_reasons
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
                )
                """,
                (
                    project_id,
                    model_version,
                    breakdown.get("freshness", 0),
                    breakdown.get("telegram_presence", 0),
                    breakdown.get("social_activity", 0),
                    breakdown.get("website_quality", 0),
                    breakdown.get("growth_rate", 0),
                    breakdown.get("source_quality", 0),
                    breakdown.get("community_activity", 0),
                    breakdown.get("spam_penalty", 0),
                    final_score,
                    score_reasons,
                ),
            )
            cur.execute(
                """
                UPDATE projects
                SET current_score = %s,
                    best_score = GREATEST(COALESCE(best_score, 0), %s),
                    status = COALESCE(%s, status),
                    last_seen_at = NOW()
                WHERE id = %s
                """,
                (final_score, final_score, project_status, project_id),
            )


def get_project(project_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM projects WHERE id = %s",
                (project_id,),
            )
            return cur.fetchone()


def list_project_scores(project_id: int, limit: int = 20) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM scores
                WHERE project_id = %s
                ORDER BY scored_at DESC
                LIMIT %s
                """,
                (project_id, limit),
            )
            return list(cur.fetchall())


def project_scored_recently(project_id: int, within_minutes: int = 30) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM scores
                WHERE project_id = %s
                  AND scored_at >= NOW() - (%s || ' minutes')::interval
                LIMIT 1
                """,
                (project_id, within_minutes),
            )
            return cur.fetchone() is not None
