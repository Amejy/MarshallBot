from __future__ import annotations

from app.db.connection import get_connection


def list_top_projects(limit: int = 30) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    p.id,
                    p.canonical_name,
                    p.chain,
                    p.website_url,
                    p.telegram_url,
                    p.x_url,
                    p.discord_url,
                    p.launch_source,
                    p.first_seen_at,
                    p.status,
                    p.current_score,
                    p.best_score
                FROM projects p
                ORDER BY COALESCE(p.current_score, 0) DESC, p.first_seen_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return list(cur.fetchall())


def list_recent_alerts(limit: int = 30) -> list[dict]:
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
                    a.score_at_send,
                    a.delivery_status,
                    a.retry_count,
                    a.next_retry_at,
                    a.last_error,
                    p.canonical_name,
                    p.chain,
                    p.website_url,
                    p.telegram_url,
                    p.launch_source,
                    sa.trust_level AS source_trust_level,
                    COALESCE(t.trust_after - t.trust_before, 0) AS source_trust_movement,
                    CASE
                        WHEN COALESCE(t.trust_after - t.trust_before, 0) > 0 THEN 'up'
                        WHEN COALESCE(t.trust_after - t.trust_before, 0) < 0 THEN 'down'
                        ELSE 'flat'
                    END AS source_trust_movement_direction
                FROM alerts_sent a
                LEFT JOIN projects p ON p.id = a.project_id
                LEFT JOIN source_accounts sa ON sa.account_identifier = p.launch_source
                LEFT JOIN LATERAL (
                    SELECT
                        h.trust_before,
                        h.trust_after
                    FROM source_account_history h
                    WHERE h.source_account_id = sa.id
                      AND h.trust_before IS NOT NULL
                      AND h.trust_after IS NOT NULL
                    ORDER BY h.changed_at DESC
                    LIMIT 1
                ) t ON TRUE
                ORDER BY a.sent_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return list(cur.fetchall())


def list_alert_health(limit: int = 20) -> dict[str, object]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE delivery_status = 'sent') AS sent_count,
                    COUNT(*) FILTER (WHERE delivery_status = 'pending') AS pending_count,
                    COUNT(*) FILTER (WHERE delivery_status = 'failed') AS failed_count,
                    COUNT(*) AS total_count
                FROM alerts_sent
                """
            )
            totals = cur.fetchone() or {}
            cur.execute(
                """
                SELECT
                    a.id,
                    a.project_id,
                    a.sent_at,
                    a.chat_id,
                    a.message_id,
                    a.score_at_send,
                    a.delivery_status,
                    a.retry_count,
                    a.next_retry_at,
                    a.last_error,
                    p.canonical_name,
                    p.chain,
                    p.website_url,
                    p.telegram_url,
                    p.launch_source
                FROM alerts_sent a
                LEFT JOIN projects p ON p.id = a.project_id
                WHERE a.delivery_status IN ('pending', 'failed')
                ORDER BY a.sent_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            issues = list(cur.fetchall())
            return {
                "totals": {
                    "sent": int(totals.get("sent_count", 0) or 0),
                    "pending": int(totals.get("pending_count", 0) or 0),
                    "failed": int(totals.get("failed_count", 0) or 0),
                    "total": int(totals.get("total_count", 0) or 0),
                },
                "issues": issues,
            }


def get_project_details(project_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    p.*,
                    COALESCE(
                        json_agg(s ORDER BY s.scored_at DESC) FILTER (WHERE s.id IS NOT NULL),
                        '[]'::json
                    ) AS scores
                FROM projects p
                LEFT JOIN scores s ON s.project_id = p.id
                WHERE p.id = %s
                GROUP BY p.id
                """,
                (project_id,),
            )
            return cur.fetchone()


def get_latest_project_score(project_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM scores
                WHERE project_id = %s
                ORDER BY scored_at DESC
                LIMIT 1
                """,
                (project_id,),
            )
            return cur.fetchone()


def list_ranking_dashboard(limit: int = 30) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    p.id,
                    p.canonical_name,
                    p.chain,
                    p.website_url,
                    p.telegram_url,
                    p.x_url,
                    p.discord_url,
                    p.launch_source,
                    sa.trust_level AS source_trust_level,
                    COALESCE(t.trust_after - t.trust_before, 0) AS source_trust_movement,
                    CASE
                        WHEN COALESCE(t.trust_after - t.trust_before, 0) > 0 THEN 'up'
                        WHEN COALESCE(t.trust_after - t.trust_before, 0) < 0 THEN 'down'
                        ELSE 'flat'
                    END AS source_trust_movement_direction,
                    p.first_seen_at,
                    p.status,
                    p.current_score,
                    p.best_score,
                    ls.scored_at,
                    ls.model_version,
                    ls.score_reasons
                FROM projects p
                LEFT JOIN source_accounts sa ON sa.account_identifier = p.launch_source
                LEFT JOIN LATERAL (
                    SELECT scored_at, model_version, score_reasons
                    FROM scores
                    WHERE project_id = p.id
                    ORDER BY scored_at DESC
                    LIMIT 1
                ) ls ON TRUE
                LEFT JOIN LATERAL (
                    SELECT
                        h.trust_before,
                        h.trust_after
                    FROM source_account_history h
                    WHERE h.source_account_id = sa.id
                      AND h.trust_before IS NOT NULL
                      AND h.trust_after IS NOT NULL
                    ORDER BY h.changed_at DESC
                    LIMIT 1
                ) t ON TRUE
                ORDER BY COALESCE(p.current_score, 0) DESC, p.first_seen_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return list(cur.fetchall())


def list_sources(limit: int = 100, status: str | None = None) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            if status:
                cur.execute(
                    """
                    SELECT *
                    FROM source_accounts
                    WHERE status = %s
                    ORDER BY trust_level DESC, last_seen_at DESC
                    LIMIT %s
                    """,
                    (status, limit),
                )
            else:
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


def list_recently_skipped_projects(limit: int = 100) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    p.id,
                    p.canonical_name,
                    p.chain,
                    p.website_url,
                    p.telegram_url,
                    p.launch_source,
                    p.current_score,
                    p.last_seen_at,
                    p.status
                FROM projects p
                WHERE EXISTS (
                    SELECT 1
                    FROM scores s
                    WHERE s.project_id = p.id
                      AND s.scored_at >= NOW() - INTERVAL '30 minutes'
                )
                ORDER BY p.last_seen_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return list(cur.fetchall())


def list_recent_social_profiles(limit: int = 50) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    sp.id,
                    sp.project_id,
                    sp.platform,
                    sp.url,
                    sp.handle,
                    sp.follower_count,
                    sp.post_count,
                    sp.engagement_score,
                    sp.created_at_estimate,
                    sp.last_checked_at,
                    sp.profile_data,
                    p.canonical_name,
                    p.chain,
                    p.website_url,
                    p.telegram_url,
                    p.x_url,
                    p.discord_url,
                    p.launch_source,
                    p.status
                FROM social_profiles sp
                LEFT JOIN projects p ON p.id = sp.project_id
                ORDER BY sp.last_checked_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return list(cur.fetchall())


def dashboard_summary() -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) AS total_projects,
                    COUNT(*) FILTER (WHERE status = 'qualified') AS qualified_projects,
                    COUNT(*) FILTER (WHERE status = 'new') AS new_projects,
                    COUNT(*) FILTER (WHERE status = 'rejected') AS rejected_projects,
                    COUNT(*) FILTER (WHERE current_score IS NOT NULL) AS scored_projects,
                    COUNT(*) FILTER (WHERE last_seen_at >= NOW() - INTERVAL '30 minutes') AS active_projects
                FROM projects
                """
            )
            row = cur.fetchone() or {}
            cur.execute(
                """
                SELECT COUNT(*) AS skipped_recently_scored
                FROM projects p
                WHERE EXISTS (
                    SELECT 1
                    FROM scores s
                    WHERE s.project_id = p.id
                      AND s.scored_at >= NOW() - INTERVAL '30 minutes'
                )
                """
            )
            skipped_row = cur.fetchone() or {}
            return {
                "total_projects": row.get("total_projects", 0),
                "qualified_projects": row.get("qualified_projects", 0),
                "new_projects": row.get("new_projects", 0),
                "rejected_projects": row.get("rejected_projects", 0),
                "scored_projects": row.get("scored_projects", 0),
                "active_projects": row.get("active_projects", 0),
                "skipped_recently_scored": skipped_row.get("skipped_recently_scored", 0),
            }


def get_project_by_name_and_chain(normalized_name: str, chain: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM projects
                WHERE normalized_name = %s
                  AND chain = %s
                """,
                (normalized_name, chain),
            )
            return cur.fetchone()


def search_projects(query: str, limit: int = 20) -> list[dict]:
    search = f"%{query.lower()}%"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    p.id,
                    p.canonical_name,
                    p.chain,
                    p.website_url,
                    p.telegram_url,
                    p.x_url,
                    p.discord_url,
                    p.launch_source,
                    sa.trust_level AS source_trust_level,
                    COALESCE(t.trust_after - t.trust_before, 0) AS source_trust_movement,
                    CASE
                        WHEN COALESCE(t.trust_after - t.trust_before, 0) > 0 THEN 'up'
                        WHEN COALESCE(t.trust_after - t.trust_before, 0) < 0 THEN 'down'
                        ELSE 'flat'
                    END AS source_trust_movement_direction,
                    p.first_seen_at,
                    p.status,
                    p.current_score,
                    p.best_score
                FROM projects p
                LEFT JOIN source_accounts sa ON sa.account_identifier = p.launch_source
                LEFT JOIN LATERAL (
                    SELECT
                        h.trust_before,
                        h.trust_after
                    FROM source_account_history h
                    WHERE h.source_account_id = sa.id
                      AND h.trust_before IS NOT NULL
                      AND h.trust_after IS NOT NULL
                    ORDER BY h.changed_at DESC
                    LIMIT 1
                ) t ON TRUE
                WHERE LOWER(p.canonical_name) LIKE %s
                   OR LOWER(p.launch_source) LIKE %s
                   OR LOWER(COALESCE(p.website_url, '')) LIKE %s
                   OR LOWER(COALESCE(p.telegram_url, '')) LIKE %s
                ORDER BY COALESCE(p.current_score, 0) DESC, p.first_seen_at DESC
                LIMIT %s
                """,
                (search, search, search, search, limit),
            )
            return list(cur.fetchall())


def list_source_trends(limit: int = 50) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    s.account_identifier,
                    s.platform,
                    s.status,
                    s.trust_level,
                    COALESCE(t.trust_after - t.trust_before, 0) AS trust_movement,
                    CASE
                        WHEN COALESCE(t.trust_after - t.trust_before, 0) > 0 THEN 'up'
                        WHEN COALESCE(t.trust_after - t.trust_before, 0) < 0 THEN 'down'
                        ELSE 'flat'
                    END AS trust_movement_direction,
                    t.changed_at AS trust_movement_changed_at,
                    COUNT(p.id) AS project_count,
                    COUNT(*) FILTER (WHERE p.status = 'qualified') AS qualified_count,
                    MAX(p.current_score) AS max_score,
                    AVG(p.current_score) AS avg_score,
                    MAX(p.last_seen_at) AS last_project_seen_at,
                    s.last_seen_at
                FROM source_accounts s
                LEFT JOIN projects p
                  ON p.launch_source = s.account_identifier
                LEFT JOIN LATERAL (
                    SELECT
                        h.changed_at,
                        h.trust_before,
                        h.trust_after
                    FROM source_account_history h
                    WHERE h.source_account_id = s.id
                      AND h.trust_before IS NOT NULL
                      AND h.trust_after IS NOT NULL
                    ORDER BY h.changed_at DESC
                    LIMIT 1
                ) t ON TRUE
                GROUP BY s.account_identifier, s.platform, s.status, s.trust_level, s.last_seen_at
                    , t.changed_at, t.trust_before, t.trust_after
                ORDER BY qualified_count DESC, project_count DESC, s.trust_level DESC
                LIMIT %s
                """,
                (limit,),
            )
            return list(cur.fetchall())


def list_source_movers(limit: int = 10) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH source_metrics AS (
                    SELECT
                        s.account_identifier,
                        s.platform,
                        s.status,
                        s.trust_level,
                        COALESCE(t.trust_after - t.trust_before, 0) AS trust_movement,
                        CASE
                            WHEN COALESCE(t.trust_after - t.trust_before, 0) > 0 THEN 'up'
                            WHEN COALESCE(t.trust_after - t.trust_before, 0) < 0 THEN 'down'
                            ELSE 'flat'
                        END AS trust_movement_direction,
                        t.changed_at AS trust_movement_changed_at,
                        COUNT(p.id) AS project_count,
                        COUNT(*) FILTER (WHERE p.status = 'qualified') AS qualified_count,
                        AVG(p.current_score) AS avg_score,
                        MAX(p.last_seen_at) AS last_project_seen_at
                    FROM source_accounts s
                    LEFT JOIN projects p
                      ON p.launch_source = s.account_identifier
                    LEFT JOIN LATERAL (
                        SELECT
                            h.changed_at,
                            h.trust_before,
                            h.trust_after
                        FROM source_account_history h
                        WHERE h.source_account_id = s.id
                          AND h.trust_before IS NOT NULL
                          AND h.trust_after IS NOT NULL
                        ORDER BY h.changed_at DESC
                        LIMIT 1
                    ) t ON TRUE
                    GROUP BY s.account_identifier, s.platform, s.status, s.trust_level, t.changed_at, t.trust_before, t.trust_after
                ),
                source_recent AS (
                    SELECT
                        s.account_identifier,
                        COUNT(p.id) FILTER (WHERE p.last_seen_at >= NOW() - INTERVAL '24 hours') AS projects_24h,
                        COUNT(*) FILTER (WHERE p.status = 'qualified' AND p.last_seen_at >= NOW() - INTERVAL '24 hours') AS qualified_24h,
                        AVG(p.current_score) FILTER (WHERE p.last_seen_at >= NOW() - INTERVAL '24 hours') AS avg_score_24h
                    FROM source_accounts s
                    LEFT JOIN projects p
                      ON p.launch_source = s.account_identifier
                    GROUP BY s.account_identifier
                )
                SELECT
                    m.account_identifier,
                    m.platform,
                    m.status,
                    m.trust_level,
                    m.trust_movement,
                    m.trust_movement_direction,
                    m.trust_movement_changed_at,
                    m.project_count,
                    m.qualified_count,
                    m.avg_score,
                    m.last_project_seen_at,
                    r.projects_24h,
                    r.qualified_24h,
                    r.avg_score_24h,
                    ROUND(
                        COALESCE(r.qualified_24h, 0) * 4.0
                        + COALESCE(r.projects_24h, 0) * 2.0
                        + COALESCE(r.avg_score_24h, 0) * 0.2,
                        2
                    ) AS momentum_score
                FROM source_metrics m
                LEFT JOIN source_recent r ON r.account_identifier = m.account_identifier
                ORDER BY momentum_score DESC, COALESCE(r.projects_24h, 0) DESC, COALESCE(r.avg_score_24h, 0) DESC
                LIMIT %s
                """,
                (limit,),
            )
            return list(cur.fetchall())


def list_source_health(limit: int = 50) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH source_metrics AS (
                    SELECT
                        s.account_identifier,
                        s.platform,
                        s.status,
                        s.trust_level,
                        s.last_seen_at,
                        COALESCE(t.trust_after - t.trust_before, 0) AS trust_movement,
                        CASE
                            WHEN COALESCE(t.trust_after - t.trust_before, 0) > 0 THEN 'up'
                            WHEN COALESCE(t.trust_after - t.trust_before, 0) < 0 THEN 'down'
                            ELSE 'flat'
                        END AS trust_movement_direction,
                        t.changed_at AS trust_movement_changed_at,
                        COUNT(p.id) AS project_count,
                        COUNT(*) FILTER (WHERE p.status = 'qualified') AS qualified_count,
                        AVG(p.current_score) AS avg_score,
                        MAX(p.last_seen_at) AS last_project_seen_at
                    FROM source_accounts s
                    LEFT JOIN projects p
                      ON p.launch_source = s.account_identifier
                    LEFT JOIN LATERAL (
                        SELECT
                            h.changed_at,
                            h.trust_before,
                            h.trust_after
                        FROM source_account_history h
                        WHERE h.source_account_id = s.id
                          AND h.trust_before IS NOT NULL
                          AND h.trust_after IS NOT NULL
                        ORDER BY h.changed_at DESC
                        LIMIT 1
                    ) t ON TRUE
                    GROUP BY s.account_identifier, s.platform, s.status, s.trust_level, s.last_seen_at, t.changed_at, t.trust_before, t.trust_after
                )
                SELECT
                    *,
                    ROUND(
                        LEAST(
                            100.0,
                            GREATEST(
                                0.0,
                                (trust_level * 0.45)
                                + LEAST(project_count, 30) * 1.5
                                + LEAST(qualified_count, 20) * 2.0
                                + COALESCE(avg_score, 0) * 0.15
                            )
                        ),
                        2
                    ) AS health_score
                FROM source_metrics
                ORDER BY health_score DESC, qualified_count DESC, project_count DESC
                LIMIT %s
                """,
                (limit,),
            )
            return list(cur.fetchall())


def get_source_health_detail(account_identifier: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH source_metrics AS (
                    SELECT
                        s.account_identifier,
                        s.platform,
                        s.status,
                        s.trust_level,
                        s.last_seen_at,
                        COALESCE(t.trust_after - t.trust_before, 0) AS trust_movement,
                        CASE
                            WHEN COALESCE(t.trust_after - t.trust_before, 0) > 0 THEN 'up'
                            WHEN COALESCE(t.trust_after - t.trust_before, 0) < 0 THEN 'down'
                            ELSE 'flat'
                        END AS trust_movement_direction,
                        t.changed_at AS trust_movement_changed_at,
                        COUNT(p.id) AS project_count,
                        COUNT(*) FILTER (WHERE p.status = 'qualified') AS qualified_count,
                        AVG(p.current_score) AS avg_score,
                        MAX(p.last_seen_at) AS last_project_seen_at
                    FROM source_accounts s
                    LEFT JOIN projects p
                      ON p.launch_source = s.account_identifier
                    LEFT JOIN LATERAL (
                        SELECT
                            h.changed_at,
                            h.trust_before,
                            h.trust_after
                        FROM source_account_history h
                        WHERE h.source_account_id = s.id
                          AND h.trust_before IS NOT NULL
                          AND h.trust_after IS NOT NULL
                        ORDER BY h.changed_at DESC
                        LIMIT 1
                    ) t ON TRUE
                    WHERE s.account_identifier = %s
                    GROUP BY s.account_identifier, s.platform, s.status, s.trust_level, s.last_seen_at, t.changed_at, t.trust_before, t.trust_after
                )
                SELECT
                    *,
                    ROUND(
                        LEAST(
                            100.0,
                            GREATEST(
                                0.0,
                                (trust_level * 0.45)
                                + LEAST(project_count, 30) * 1.5
                                + LEAST(qualified_count, 20) * 2.0
                                + COALESCE(avg_score, 0) * 0.15
                            )
                        ),
                        2
                    ) AS health_score
                FROM source_metrics
                LIMIT 1
                """,
                (account_identifier,),
            )
            return cur.fetchone()


def list_source_recent_projects(account_identifier: str, limit: int = 5) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    p.id,
                    p.canonical_name,
                    p.chain,
                    p.website_url,
                    p.telegram_url,
                    p.x_url,
                    p.discord_url,
                    p.launch_source,
                    p.first_seen_at,
                    p.last_seen_at,
                    p.status,
                    p.current_score,
                    p.best_score
                FROM projects p
                WHERE p.launch_source = %s
                ORDER BY p.last_seen_at DESC, p.first_seen_at DESC
                LIMIT %s
                """,
                (account_identifier, limit),
            )
            return list(cur.fetchall())


def list_top_today_projects(limit: int = 30) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    p.id,
                    p.canonical_name,
                    p.chain,
                    p.website_url,
                    p.telegram_url,
                    p.x_url,
                    p.discord_url,
                    p.launch_source,
                    sa.trust_level AS source_trust_level,
                    COALESCE(t.trust_after - t.trust_before, 0) AS source_trust_movement,
                    CASE
                        WHEN COALESCE(t.trust_after - t.trust_before, 0) > 0 THEN 'up'
                        WHEN COALESCE(t.trust_after - t.trust_before, 0) < 0 THEN 'down'
                        ELSE 'flat'
                    END AS source_trust_movement_direction,
                    p.first_seen_at,
                    p.status,
                    p.current_score,
                    p.best_score,
                    s.scored_at,
                    s.model_version,
                    s.score_reasons
                FROM projects p
                LEFT JOIN source_accounts sa ON sa.account_identifier = p.launch_source
                LEFT JOIN LATERAL (
                    SELECT scored_at, model_version, score_reasons
                    FROM scores
                    WHERE project_id = p.id
                    ORDER BY scored_at DESC
                    LIMIT 1
                ) s ON TRUE
                LEFT JOIN LATERAL (
                    SELECT
                        h.trust_before,
                        h.trust_after
                    FROM source_account_history h
                    WHERE h.source_account_id = sa.id
                      AND h.trust_before IS NOT NULL
                      AND h.trust_after IS NOT NULL
                    ORDER BY h.changed_at DESC
                    LIMIT 1
                ) t ON TRUE
                WHERE p.first_seen_at >= NOW() - INTERVAL '24 hours'
                   OR p.last_seen_at >= NOW() - INTERVAL '24 hours'
                ORDER BY COALESCE(p.current_score, 0) DESC, p.first_seen_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return list(cur.fetchall())


def dashboard_activity() -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE first_seen_at >= NOW() - INTERVAL '24 hours') AS discovered_today,
                    COUNT(*) FILTER (WHERE current_score IS NOT NULL AND last_seen_at >= NOW() - INTERVAL '24 hours') AS active_today,
                    COUNT(*) FILTER (WHERE status = 'qualified' AND last_seen_at >= NOW() - INTERVAL '24 hours') AS qualified_today,
                    COUNT(*) FILTER (WHERE status = 'rejected' AND last_seen_at >= NOW() - INTERVAL '24 hours') AS rejected_today
                FROM projects
                """
            )
            row = cur.fetchone() or {}
            return {
                "discovered_today": row.get("discovered_today", 0),
                "active_today": row.get("active_today", 0),
                "qualified_today": row.get("qualified_today", 0),
                "rejected_today": row.get("rejected_today", 0),
            }
