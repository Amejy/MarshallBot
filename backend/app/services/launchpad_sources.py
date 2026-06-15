from __future__ import annotations

from app.services.connectors import SitemapSource


class FourMemeSource(SitemapSource):
    def __init__(self, url: str = "https://four.meme", limit: int = 50) -> None:
        super().__init__("four-meme", url, chain="bsc", max_pages=limit)
