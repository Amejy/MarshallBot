from __future__ import annotations

from app.services.filters import passes_hard_filters
from app.services.ranking import RankingConfig


def should_keep_project(
    project: dict,
    score: float,
    config: RankingConfig,
    blacklisted_domains: list[str] | None = None,
    blacklisted_telegram: list[str] | None = None,
) -> bool:
    project_age_hours = project.get("project_age_hours")
    try:
        if project_age_hours is not None and float(project_age_hours) > float(config.max_project_age_hours):
            return False
    except (TypeError, ValueError):
        pass
    if not passes_hard_filters(
        project,
        blacklisted_domains=blacklisted_domains,
        blacklisted_telegram=blacklisted_telegram,
    ):
        return False
    return score >= config.min_score_to_alert
