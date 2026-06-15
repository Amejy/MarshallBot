from __future__ import annotations

from app.services.sources import DiscoverySource


class CollectorRegistry:
    def __init__(self) -> None:
        self._sources: dict[str, DiscoverySource] = {}

    def register(self, name: str, source: DiscoverySource) -> None:
        self._sources[name] = source

    def get(self, name: str) -> DiscoverySource:
        return self._sources[name]

    def names(self) -> list[str]:
        return sorted(self._sources.keys())

