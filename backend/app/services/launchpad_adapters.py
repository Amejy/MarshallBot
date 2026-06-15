from __future__ import annotations

from abc import ABC, abstractmethod

from app.services.sources import DiscoverySource


class LaunchpadAdapter(DiscoverySource, ABC):
    @property
    @abstractmethod
    def launchpad_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def chain(self) -> str:
        raise NotImplementedError


class StaticLaunchpadAdapter(LaunchpadAdapter):
    def __init__(self, launchpad_name: str, chain: str, items: list[dict]) -> None:
        self._launchpad_name = launchpad_name
        self._chain = chain
        self.items = items

    @property
    def launchpad_name(self) -> str:
        return self._launchpad_name

    @property
    def chain(self) -> str:
        return self._chain

    def collect(self) -> list[dict]:
        return [
            dict(
                item,
                chain=item.get("chain", self.chain),
                launch_source=self.launchpad_name,
                source_type="launchpad",
                source_name=self.launchpad_name,
            )
            for item in self.items
        ]

