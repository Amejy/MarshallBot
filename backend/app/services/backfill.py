from __future__ import annotations

from app.core.source_config import SourceConfig
from app.services.orchestration import process_source
from app.services.ranking import RankingConfig
from app.services.registry import build_default_registry


def backfill_source(source_name: str, source_config: SourceConfig, config: RankingConfig, limit: int | None = None) -> dict:
    registry = build_default_registry(source_config)
    source = registry.get(source_name)

    class _LimitedSource:
        def collect(self) -> list[dict]:
            items = source.collect()
            if limit is None:
                return items
            return items[: max(0, limit)]

    results = process_source(
        _LimitedSource(),
        config,
        source_config=source_config,
        enrich_websites=True,
        score_cooldown_minutes=0,
    )
    return {
        "source": source_name,
        "count": len(results),
        "kept": len([item for item in results if item.get("keep")]),
        "selected": len([item for item in results if item.get("selected")]),
        "results": results,
    }
