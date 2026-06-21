from __future__ import annotations

from app.services.decision import should_keep_project
from app.services.enrichment import enrich_website, website_quality_score
from app.services.filters import looks_like_spam, spam_penalty
from app.services.pipeline import build_default_signals, ingest_discovery_event, evaluate_project
from app.services.ranking import RankingConfig
from app.services.selection import select_top_opportunities
from app.services.sources import DiscoverySource
from app.db.repository import adjust_source_trust, persist_score, store_website_snapshot, upsert_project
from app.db.repository import project_scored_recently, upsert_social_profile, upsert_source_account
from app.core.source_config import SourceConfig
from app.services.pumpfun import enrich_pumpfun_project
from app.core.dedupe import fingerprint, normalize_name


def _safe_db_call(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception:
        return None


def _safe_persist_score(project_id: int, model_version: str, breakdown: dict, final_score: float, score_reasons: dict, project_status: str | None = None) -> None:
    _safe_db_call(
        persist_score,
        project_id,
        model_version,
        breakdown,
        final_score,
        score_reasons,
        project_status,
    )


def _fallback_project(event: dict) -> dict:
    synthetic_id = int(fingerprint(
        str(event.get("canonical_name", "")),
        str(event.get("website_url", "")),
        str(event.get("telegram_url", "")),
    )[:12], 16)
    return {
        "id": synthetic_id,
        "canonical_name": event.get("canonical_name"),
        "chain": event.get("chain"),
        "website_url": event.get("website_url"),
        "telegram_url": event.get("telegram_url"),
        "x_url": event.get("x_url"),
        "discord_url": event.get("discord_url"),
        "launch_source": event.get("launch_source", "unknown"),
        "first_seen_at": event.get("first_seen_at"),
        "status": event.get("status", "new"),
    }


def _safe_ingest_discovery_event(event: dict) -> dict:
    try:
        return ingest_discovery_event(event)
    except Exception:
        return _fallback_project(event)


def _safe_project_scored_recently(project_id: int, within_minutes: int) -> bool:
    try:
        return project_scored_recently(project_id, within_minutes=within_minutes)
    except Exception:
        return False


def _social_profile_entries(project: dict, event: dict) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    profile_data = {
        "project_name": project.get("canonical_name"),
        "launch_source": project.get("launch_source"),
        "source_type": event.get("source_type"),
        "source_name": event.get("source_name"),
        "raw_payload": event,
    }
    for platform, url_key in ("telegram", "telegram_url"), ("x", "x_url"), ("discord", "discord_url"):
        url = project.get(url_key) or event.get(url_key)
        if not url:
            continue
        entries.append(
            {
                "platform": platform,
                "url": str(url),
                "handle": None,
                "profile_data": profile_data,
            }
        )
    return entries


def _merge_website_links(project: dict, website: dict) -> dict:
    merged = dict(project)
    parsed_data = website.get("parsed_data") or {}
    for field_name, parsed_key in (
        ("telegram_url", "telegram_links"),
        ("x_url", "x_links"),
        ("discord_url", "discord_links"),
    ):
        links = parsed_data.get(parsed_key) or []
        if links and not merged.get(field_name):
            merged[field_name] = links[0]
    return merged


def process_source(
    source: DiscoverySource,
    config: RankingConfig,
    source_config: SourceConfig | None = None,
    default_signals: dict | None = None,
    enrich_websites: bool = True,
    score_cooldown_minutes: int = 30,
) -> list[dict]:
    source_config = source_config or SourceConfig()
    results: list[dict] = []
    for event in source.collect():
        source_account = _safe_db_call(
            upsert_source_account,
            str(event.get("source_type", "unknown")),
            str(event.get("source_name", "unknown")),
            trust_level=80.0
            if str(event.get("source_name", "")).lower() in {item.lower() for item in source_config.trusted_sources}
            else 50.0,
            metadata={"launch_source": event.get("launch_source")},
        )
        current_trust_level = float((source_account or {}).get("trust_level", 0) or 0)
        project = _safe_ingest_discovery_event(event)
        if project.get("id"):
            for profile in _social_profile_entries(project, event):
                _safe_db_call(
                    upsert_social_profile,
                    int(project["id"]),
                    str(profile["platform"]),
                    str(profile["url"]),
                    handle=profile.get("handle"),
                    profile_data=profile.get("profile_data"),
                )
        if event.get("launch_source") == "pump-fun" and event.get("pumpfun_url"):
            project = enrich_pumpfun_project(project)
        if project.get("id") and _safe_project_scored_recently(int(project["id"]), within_minutes=score_cooldown_minutes):
            results.append(
                {
                    "project_id": project.get("id"),
                    "canonical_name": project.get("canonical_name"),
                    "chain": project.get("chain"),
                    "website_url": project.get("website_url"),
                    "telegram_url": project.get("telegram_url"),
                    "launch_source": project.get("launch_source"),
                    "score": project.get("current_score") or 0,
                    "keep": False,
                    "selected": False,
                    "skipped_reason": "recently_scored",
                }
            )
            continue
        website = None
        signals = build_default_signals(
            event,
            project=project,
            source_config=source_config,
            default_signals={**(default_signals or {}), "source_trust_level": current_trust_level},
        )
        signals["spam_penalty"] = spam_penalty(event)

        if enrich_websites and project.get("website_url"):
            try:
                website = enrich_website(str(project["website_url"]))
                project = _merge_website_links(project, website)
                if project.get("id"):
                    _safe_db_call(upsert_project, project)
                signals = build_default_signals(
                    event,
                    project=project,
                    source_config=source_config,
                    default_signals={**(default_signals or {}), "source_trust_level": current_trust_level},
                )
                signals["spam_penalty"] = spam_penalty(event)
                signals["website_quality"] = website_quality_score(website["parsed_data"], chain=str(project.get("chain")))
                signals["spam_penalty"] = max(float(signals.get("spam_penalty", 0)), spam_penalty({**event, **website}))
            except Exception:
                signals["website_quality"] = max(float(signals.get("website_quality", 0)), 10.0)

        evaluated = evaluate_project(project, signals)
        evaluated["keep"] = should_keep_project(
            {**project, "project_age_hours": evaluated.get("project_age_hours")},
            evaluated["score"],
            config,
            blacklisted_domains=source_config.blacklisted_domains,
            blacklisted_telegram=source_config.blacklisted_telegram,
        )
        if looks_like_spam({**project, **event, **evaluated, **signals}):
            evaluated["keep"] = False
            evaluated["score"] = min(float(evaluated["score"]), 35.0)
        if evaluated.get("project_id"):
            _safe_persist_score(
                int(evaluated["project_id"]),
                "v1",
                evaluated["breakdown"],
                float(evaluated["score"]),
                evaluated["score_reasons"],
                project_status="qualified" if evaluated.get("keep") else None,
            )
        if evaluated["keep"] and evaluated.get("project_id"):
            current_trust = 80.0 if str(event.get("source_name", "")).lower() in {item.lower() for item in source_config.trusted_sources} else 50.0
            _safe_db_call(
                upsert_source_account,
                str(event.get("source_type", "unknown")),
                str(event.get("source_name", "unknown")),
                trust_level=min(100.0, current_trust + 5.0),
                metadata={"positive_signal": True},
            )
        if project.get("id"):
            updated_trust = _safe_db_call(
                adjust_source_trust,
                str(event.get("source_name", "unknown")),
                float(evaluated.get("score", 0)),
                bool(evaluated.get("keep")),
                looks_like_spam({**project, **event, **evaluated, **signals}),
                note="qualified" if evaluated.get("keep") else "filtered",
            )
            if updated_trust is not None:
                evaluated["source_trust_movement"] = float(updated_trust) - float(current_trust)
                evaluated["source_trust_movement_direction"] = (
                    "up"
                    if evaluated["source_trust_movement"] > 0
                    else "down"
                    if evaluated["source_trust_movement"] < 0
                    else "flat"
                )
                evaluated["source_trust_updated"] = float(updated_trust)
        if website and evaluated.get("project_id"):
            _safe_db_call(store_website_snapshot, int(evaluated["project_id"]), website)
        results.append(evaluated)
    selected = select_top_opportunities(results, config.daily_alert_limit)
    for item in results:
        item["selected"] = item in selected
    return results


def reprocess_project(project: dict, source_config: SourceConfig, config: RankingConfig, enrich_websites: bool = True) -> dict:
    event = {
        "canonical_name": project["canonical_name"],
        "chain": project["chain"],
        "website_url": project.get("website_url"),
        "telegram_url": project.get("telegram_url"),
        "x_url": project.get("x_url"),
        "discord_url": project.get("discord_url"),
        "launch_source": project.get("launch_source", "manual"),
        "source_type": "manual",
        "source_name": project.get("launch_source", "manual"),
    }
    class _SingleEventSource:
        def collect(self) -> list[dict]:
            return [event]

    result = process_source(
        _SingleEventSource(),
        config,
        source_config=source_config,
        enrich_websites=enrich_websites,
        score_cooldown_minutes=0,
    )
    return result[0] if result else {"status": "no_result", "normalized_name": normalize_name(project["canonical_name"])}
