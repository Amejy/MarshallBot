from __future__ import annotations

from dataclasses import dataclass

from app.core.scoring import ScoreBreakdown
from app.services.trust import source_noise_penalty, source_trust_score


@dataclass(slots=True)
class RankingConfig:
    min_score_to_alert: float = 75.0
    daily_alert_limit: int = 30
    max_project_age_hours: float = 24.0
    max_pair_age_hours: float = 24.0


DEFAULT_WEIGHTS: dict[str, float] = {
    "freshness": 0.25,
    "telegram_presence": 0.14,
    "social_activity": 0.12,
    "website_quality": 0.18,
    "growth_rate": 0.12,
    "source_quality": 0.08,
    "community_activity": 0.11,
    "spam_penalty": 0.10,
}


def _weight(weights: dict[str, float], key: str) -> float:
    return float(weights.get(key, DEFAULT_WEIGHTS[key]))


def compute_score(signals: dict) -> tuple[float, dict]:
    trusted_sources = list(signals.get("trusted_sources", []))
    source_name = str(signals.get("source_name", ""))
    source_trust_level = float(signals.get("source_trust_level", 0) or 0)
    weights = dict(DEFAULT_WEIGHTS)
    weights.update({key: float(value) for key, value in dict(signals.get("weights", {})).items()})
    breakdown = ScoreBreakdown(
        freshness=float(signals.get("freshness", 0)),
        telegram_presence=float(signals.get("telegram_presence", 0)),
        social_activity=float(signals.get("social_activity", 0)),
        website_quality=float(signals.get("website_quality", 0)),
        growth_rate=float(signals.get("growth_rate", 0)),
        source_quality=max(
            float(signals.get("source_quality", 0)),
            source_trust_score(source_name, trusted_sources, source_trust_level=source_trust_level),
        ),
        community_activity=float(signals.get("community_activity", 0)),
        spam_penalty=float(signals.get("spam_penalty", 0))
        + source_noise_penalty(source_name, trusted_sources, source_trust_level=source_trust_level),
    )
    score = (
        _weight(weights, "freshness") * breakdown.freshness
        + _weight(weights, "telegram_presence") * breakdown.telegram_presence
        + _weight(weights, "social_activity") * breakdown.social_activity
        + _weight(weights, "website_quality") * breakdown.website_quality
        + _weight(weights, "growth_rate") * breakdown.growth_rate
        + _weight(weights, "source_quality") * breakdown.source_quality
        + _weight(weights, "community_activity") * breakdown.community_activity
        - _weight(weights, "spam_penalty") * breakdown.spam_penalty
    )
    final_score = round(max(0.0, min(100.0, score)), 2)
    return final_score, {
        "freshness": breakdown.freshness,
        "telegram_presence": breakdown.telegram_presence,
        "social_activity": breakdown.social_activity,
        "website_quality": breakdown.website_quality,
        "growth_rate": breakdown.growth_rate,
        "source_quality": breakdown.source_quality,
        "community_activity": breakdown.community_activity,
        "spam_penalty": breakdown.spam_penalty,
        "source_name": source_name,
        "source_trust_level": source_trust_level,
        "weights": weights,
    }
