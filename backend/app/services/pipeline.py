from __future__ import annotations

from datetime import datetime, timezone
from app.core.dedupe import fingerprint
from app.core.scoring import ScoreBreakdown, score_explanations
from app.db.repository import (
    insert_project_event,
    persist_score,
    project_fingerprint,
    record_dedupe_fingerprint,
    upsert_project,
)
from app.services.ranking import compute_score
from app.services.sources import DiscoverySource


def normalize_event(event: dict) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "canonical_name": event["canonical_name"],
        "chain": event["chain"],
        "website_url": event.get("website_url"),
        "telegram_url": event.get("telegram_url"),
        "x_url": event.get("x_url"),
        "discord_url": event.get("discord_url"),
        "launch_source": event.get("launch_source", "unknown"),
        "first_seen_at": event.get("first_seen_at", now),
        "status": event.get("status", "new"),
    }


def ingest_discovery_event(event: dict) -> dict:
    project_record = normalize_event(event)
    project_record["risk_flags"] = {
        key: value
        for key, value in event.items()
        if key
        in {
            "pair_created_at",
            "token_address",
            "pair_address",
            "liquidity_usd",
            "liquidity_base",
            "liquidity_quote",
            "volume_24h",
            "fdv",
            "market_cap",
            "price_usd",
            "dexscreener_url",
            "profile_url",
        }
        and value is not None
    }
    project = upsert_project(project_record)
    if project.get("id"):
        insert_project_event(
            int(project["id"]),
            event.get("source_type", "unknown"),
            event.get("source_name", "unknown"),
            event,
        )
        record_dedupe_fingerprint("project", project_fingerprint(project), int(project["id"]))
    return project


def _signal_text(event: dict, project: dict) -> str:
    parts = [
        str(event.get("canonical_name", "")),
        str(event.get("launch_source", "")),
        str(event.get("source_name", "")),
        str(event.get("raw_text", "")),
        str(project.get("website_url", "")),
        str(project.get("telegram_url", "")),
        str(project.get("x_url", "")),
        str(project.get("discord_url", "")),
    ]
    return " ".join(part for part in parts if part).lower()


def _coerce_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric > 1_000_000_000_000:
            numeric /= 1000.0
        return datetime.fromtimestamp(numeric, tz=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        numeric = float(text)
        if numeric > 1_000_000_000_000:
            numeric /= 1000.0
        return datetime.fromtimestamp(numeric, tz=timezone.utc)
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _project_age_hours(event: dict, project: dict) -> float | None:
    for key in ("pair_created_at", "first_seen_at", "created_at", "published_at"):
        dt = _coerce_datetime(project.get(key) or event.get(key))
        if dt is not None:
            delta = datetime.now(timezone.utc) - dt.astimezone(timezone.utc)
            return max(0.0, delta.total_seconds() / 3600.0)
    return None


def _freshness_from_age(age_hours: float | None, source_type: str | None = None, chain: str | None = None) -> float:
    if age_hours is None:
        if source_type == "launchpad":
            return 92.0
        if source_type == "telegram":
            return 84.0
        return 72.0

    # Freshness drops quickly as a project ages so late-stage tokens stop
    # outranking genuinely new launches.
    if age_hours <= 1:
        freshness = 100.0
    elif age_hours <= 3:
        freshness = 96.0
    elif age_hours <= 6:
        freshness = 90.0
    elif age_hours <= 12:
        freshness = 82.0
    elif age_hours <= 24:
        freshness = 72.0
    elif age_hours <= 48:
        freshness = 55.0
    elif age_hours <= 72:
        freshness = 38.0
    else:
        freshness = 15.0

    if source_type == "launchpad":
        freshness += 4.0
    elif source_type == "telegram":
        freshness += 2.0
    if chain == "solana" and age_hours <= 6:
        freshness += 2.0
    return max(0.0, min(100.0, freshness))


def _social_velocity_score(event: dict, project: dict, chain: str | None, source_type: str | None = None) -> tuple[float, float]:
    has_telegram = bool(project.get("telegram_url") or event.get("telegram_url"))
    has_x = bool(project.get("x_url") or event.get("x_url"))
    has_discord = bool(project.get("discord_url") or event.get("discord_url"))
    text = _signal_text(event, project)
    social_channels = int(has_telegram) + int(has_x) + int(has_discord)

    social_activity = 18.0 + social_channels * 18.0
    community_activity = 14.0 + social_channels * 16.0

    if has_telegram:
        social_activity += 12.0
        community_activity += 10.0
    if has_x:
        social_activity += 12.0
    if has_discord:
        social_activity += 10.0
        community_activity += 12.0

    if any(term in text for term in ("community", "holders", "holder", "raid", "engage", "engagement")):
        social_activity += 8.0
        community_activity += 10.0
    if any(term in text for term in ("fair launch", "launch", "live now", "presale", "whitelist", "airdrop")):
        social_activity += 6.0
    if any(term in text for term in ("tokenomics", "roadmap", "whitepaper", "docs")):
        community_activity += 6.0

    if chain == "bsc":
        community_activity += 4.0 if has_discord else 0.0
        social_activity += 4.0 if has_x else 0.0
    elif chain == "solana":
        community_activity += 4.0 if has_telegram else 0.0
        social_activity += 4.0 if has_x else 0.0

    if source_type == "telegram" and has_telegram:
        community_activity += 8.0
        social_activity += 4.0

    return min(100.0, social_activity), min(100.0, community_activity)


def build_default_signals(
    event: dict,
    project: dict | None = None,
    source_config: object | None = None,
    default_signals: dict | None = None,
) -> dict:
    project = project or {}
    source_config = source_config or {}
    if isinstance(source_config, dict):
        trusted_sources = [str(item).lower() for item in source_config.get("trusted_sources", [])]
    else:
        trusted_sources = [str(item).lower() for item in getattr(source_config, "trusted_sources", [])]
    source_name = str(event.get("source_name", ""))
    launch_source = str(event.get("launch_source", ""))
    source_type = str(event.get("source_type", ""))
    chain = str(project.get("chain") or event.get("chain") or "").lower()
    age_hours = _project_age_hours(event, project)
    has_website = bool(project.get("website_url") or event.get("website_url"))
    has_telegram = bool(project.get("telegram_url") or event.get("telegram_url"))
    has_x = bool(project.get("x_url") or event.get("x_url"))
    has_discord = bool(project.get("discord_url") or event.get("discord_url"))
    social_activity, community_activity = _social_velocity_score(event, project, chain, source_type)
    is_trusted = source_name.lower() in trusted_sources
    is_launchpad = source_type == "launchpad" or launch_source in {"pump-fun", "four-meme"}
    is_research = source_type == "telegram"
    source_trust_level = float(default_signals.get("source_trust_level", 0) if default_signals else 0)
    if not source_trust_level:
        source_trust_level = 88.0 if is_trusted else 78.0 if is_launchpad else 72.0 if is_research else 55.0

    signals = dict(default_signals or {})
    signals.setdefault("freshness", _freshness_from_age(age_hours, source_type=source_type, chain=chain))
    signals.setdefault("telegram_presence", 92 if has_telegram else 0)
    signals.setdefault("social_activity", social_activity)
    signals.setdefault("website_quality", 55 if has_website else 0)
    signals.setdefault("growth_rate", 50 if is_launchpad and chain == "bsc" else 45 if is_launchpad else 35 if is_research else 28)
    signals.setdefault("source_quality", 85 if is_trusted else 75 if is_launchpad else 70 if is_research else 55)
    signals.setdefault("community_activity", community_activity)
    signals.setdefault("spam_penalty", 0)
    signals.setdefault("project_age_hours", age_hours)
    signals.setdefault("source_name", source_name)
    signals.setdefault("trusted_sources", trusted_sources)
    signals.setdefault("source_trust_level", source_trust_level)
    return signals


def evaluate_project(project: dict, signals: dict) -> dict:
    score, breakdown = compute_score(signals)
    breakdown_model = ScoreBreakdown(
        freshness=float(breakdown.get("freshness", 0)),
        telegram_presence=float(breakdown.get("telegram_presence", 0)),
        social_activity=float(breakdown.get("social_activity", 0)),
        website_quality=float(breakdown.get("website_quality", 0)),
        growth_rate=float(breakdown.get("growth_rate", 0)),
        source_quality=float(breakdown.get("source_quality", 0)),
        community_activity=float(breakdown.get("community_activity", 0)),
        spam_penalty=float(breakdown.get("spam_penalty", 0)),
    )
    return {
        "project_id": project.get("id"),
        "canonical_name": project.get("canonical_name"),
        "chain": project.get("chain"),
        "website_url": project.get("website_url"),
        "telegram_url": project.get("telegram_url"),
        "x_url": project.get("x_url"),
        "discord_url": project.get("discord_url"),
        "launch_source": project.get("launch_source"),
        "first_seen_at": project.get("first_seen_at"),
        "project_age_hours": signals.get("project_age_hours"),
        "score": score,
        "breakdown": breakdown,
        "score_explanations": score_explanations(breakdown_model),
        "score_reasons": {
            "signals": breakdown,
            "explanations": score_explanations(breakdown_model),
        },
        "source_trust_level": float(signals.get("source_trust_level", 0) or 0),
        "source_name": str(signals.get("source_name", "")),
        "dedupe_key": fingerprint(
            str(project.get("canonical_name", "")),
            str(project.get("website_url", "")),
            str(project.get("telegram_url", "")),
        ),
    }


def run_source(source: DiscoverySource, default_signals: dict | None = None) -> list[dict]:
    results: list[dict] = []
    for event in source.collect():
        project = ingest_discovery_event(event)
        signals = build_default_signals(
            event,
            project=project,
            source_config={"trusted_sources": event.get("trusted_sources", [])},
            default_signals=default_signals,
        )
        evaluated = evaluate_project(project, signals)
        if evaluated.get("project_id"):
            persist_score(
                int(evaluated["project_id"]),
                "v1",
                evaluated["breakdown"],
                float(evaluated["score"]),
                evaluated["score_reasons"],
                project_status="qualified" if float(evaluated["score"]) >= 75 else "new",
            )
        results.append(evaluated)
    return results
