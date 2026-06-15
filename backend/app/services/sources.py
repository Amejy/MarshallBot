from __future__ import annotations

from abc import ABC, abstractmethod


class DiscoverySource(ABC):
    @abstractmethod
    def collect(self) -> list[dict]:
        raise NotImplementedError


class StaticDiscoverySource(DiscoverySource):
    def __init__(self, items: list[dict]) -> None:
        self.items = items

    def collect(self) -> list[dict]:
        return list(self.items)


class CompositeDiscoverySource(DiscoverySource):
    def __init__(self, sources: list[DiscoverySource]) -> None:
        self.sources = sources

    def collect(self) -> list[dict]:
        items: list[dict] = []
        for source in self.sources:
            items.extend(source.collect())
        return items
