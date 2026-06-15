from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.dedupe import normalize_domain, normalize_name


@dataclass(slots=True)
class DiscoveredProject:
    canonical_name: str
    chain: str
    website_url: str | None
    telegram_url: str | None
    x_url: str | None = None
    discord_url: str | None = None
    launch_source: str = ""
    first_seen_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def normalized_name(self) -> str:
        return normalize_name(self.canonical_name)

    @property
    def website_domain(self) -> str | None:
        if not self.website_url:
            return None
        return normalize_domain(self.website_url)


def is_eligible(project: DiscoveredProject) -> bool:
    return bool(project.website_url and project.telegram_url)

