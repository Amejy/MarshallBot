from app.core.scoring import ScoreBreakdown, score_explanations, should_alert
from app.services.ranking import compute_score
from app.services.trust import source_noise_penalty, source_trust_score
from app.db.repository import _next_source_trust


def test_final_score_caps_at_100() -> None:
    breakdown = ScoreBreakdown(
        freshness=100,
        telegram_presence=100,
        social_activity=100,
        website_quality=100,
        growth_rate=100,
        source_quality=100,
        community_activity=100,
        spam_penalty=0,
    )

    assert breakdown.final_score() == 100.0


def test_should_alert_threshold() -> None:
    assert should_alert(80.0, 75.0) is True
    assert should_alert(70.0, 75.0) is False


def test_score_explanations_surface_good_signals() -> None:
    breakdown = ScoreBreakdown(
        freshness=80,
        telegram_presence=80,
        social_activity=70,
        website_quality=75,
        growth_rate=60,
        source_quality=90,
        community_activity=65,
        spam_penalty=0,
    )

    explanations = score_explanations(breakdown)
    assert "Telegram link present" in explanations
    assert "Website looks complete" in explanations
    assert "Trusted discovery source" in explanations


def test_compute_score_honors_custom_weights() -> None:
    default_score, _ = compute_score(
        {
            "freshness": 100,
            "telegram_presence": 0,
            "social_activity": 0,
            "website_quality": 0,
            "growth_rate": 0,
            "source_quality": 0,
            "community_activity": 0,
            "spam_penalty": 0,
            "source_name": "demo",
            "trusted_sources": [],
        }
    )
    boosted_score, _ = compute_score(
        {
            "freshness": 100,
            "telegram_presence": 0,
            "social_activity": 0,
            "website_quality": 0,
            "growth_rate": 0,
            "source_quality": 0,
            "community_activity": 0,
            "spam_penalty": 0,
            "source_name": "demo",
            "trusted_sources": [],
            "weights": {"freshness": 0.5, "spam_penalty": 0.0},
        }
    )

    assert boosted_score > default_score


def test_compute_score_exposes_source_trust_level() -> None:
    _, breakdown = compute_score(
        {
            "freshness": 50,
            "telegram_presence": 50,
            "social_activity": 50,
            "website_quality": 50,
            "growth_rate": 50,
            "source_quality": 50,
            "community_activity": 50,
            "spam_penalty": 0,
            "source_name": "demo",
            "trusted_sources": [],
            "source_trust_level": 82,
        }
    )

    assert breakdown["source_trust_level"] == 82


def test_source_trust_helpers_respect_trust_level() -> None:
    assert source_trust_score("demo", [], source_trust_level=91) == 91.0
    assert source_noise_penalty("demo", [], source_trust_level=91) == 1.0
    assert source_noise_penalty("demo", [], source_trust_level=60) == 6.0


def test_next_source_trust_moves_with_outcome() -> None:
    qualified = _next_source_trust(60, 90, True)
    filtered = _next_source_trust(60, 30, False)

    assert qualified > 60
    assert filtered < 60
