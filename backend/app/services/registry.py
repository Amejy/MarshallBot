from __future__ import annotations

from app.core.source_config import SourceConfig
from app.services.collector_registry import CollectorRegistry
from app.services.source_builder import build_source_registry


def build_default_registry(config: SourceConfig | None = None) -> CollectorRegistry:
    config = config or SourceConfig.load()
    registry = CollectorRegistry()
    for name, source in build_source_registry(config).items():
        registry.register(name, source)  # type: ignore[arg-type]
    return registry
