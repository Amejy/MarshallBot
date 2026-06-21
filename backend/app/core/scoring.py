from dataclasses import dataclass


@dataclass(slots=True)
class ScoreBreakdown:
    freshness: float = 0.0
    telegram_presence: float = 0.0
    social_activity: float = 0.0
    website_quality: float = 0.0
    growth_rate: float = 0.0
    source_quality: float = 0.0
    community_activity: float = 0.0
    spam_penalty: float = 0.0

    def final_score(self) -> float:
        score = (
            0.25 * self.freshness
            + 0.14 * self.telegram_presence
            + 0.12 * self.social_activity
            + 0.18 * self.website_quality
            + 0.12 * self.growth_rate
            + 0.08 * self.source_quality
            + 0.11 * self.community_activity
            - 0.10 * self.spam_penalty
        )
        return round(max(0.0, min(100.0, score)), 2)


def should_alert(score: float, min_score: float) -> bool:
    return score >= min_score


def score_explanations(breakdown: ScoreBreakdown) -> list[str]:
    reasons: list[str] = []

    if breakdown.telegram_presence >= 70:
        reasons.append("Telegram link present")
    elif breakdown.telegram_presence <= 10:
        reasons.append("No usable Telegram signal")

    if breakdown.website_quality >= 70:
        reasons.append("Website looks complete")
    elif breakdown.website_quality <= 20:
        reasons.append("Website looks thin")

    if breakdown.social_activity >= 60:
        reasons.append("Strong social activity")
    if breakdown.community_activity >= 60:
        reasons.append("Healthy community activity")
    if breakdown.source_quality >= 80:
        reasons.append("Trusted discovery source")
    if breakdown.spam_penalty >= 30:
        reasons.append("Spam signals detected")
    if not reasons:
        reasons.append("Balanced but unremarkable signal mix")

    return reasons
