from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen

from app.services.extractor import extract_links, extract_social_links
from app.services.sources import DiscoverySource


def fetch_text(url: str, timeout: int = 20) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "MarshallBot/0.1 (+https://example.invalid)",
            "Accept": "*/*",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def fetch_json(url: str, timeout: int = 20):
    return json.loads(fetch_text(url, timeout=timeout))


URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
SITEMAP_DIRECTIVE_RE = re.compile(r"^\s*Sitemap:\s*(\S+)\s*$", re.IGNORECASE | re.MULTILINE)


def _first_url(text: str | None, exclude_social: bool = True) -> str | None:
    if not text:
        return None
    social_hosts = ("t.me/", "telegram.me/", "x.com/", "twitter.com/", "discord.gg/", "discord.com/")
    for match in URL_RE.findall(text):
        cleaned = match.rstrip(").,]}>")
        if exclude_social and any(host in cleaned.lower() for host in social_hosts):
            continue
        return cleaned
    return None


class JSONFeedSource(DiscoverySource):
    def __init__(self, name: str, url: str, chain: str, items_path: str = "items") -> None:
        self.name = name
        self.url = url
        self.chain = chain
        self.items_path = items_path

    def collect(self) -> list[dict]:
        payload = json.loads(fetch_text(self.url))
        items = payload.get(self.items_path, payload if isinstance(payload, list) else [])
        results: list[dict] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            results.append(
                dict(
                    item,
                    chain=item.get("chain", self.chain),
                    launch_source=self.name,
                    source_type="launchpad",
                    source_name=self.name,
                )
            )
        return results


class RSSFeedSource(DiscoverySource):
    def __init__(self, name: str, url: str, chain: str) -> None:
        self.name = name
        self.url = url
        self.chain = chain

    def collect(self) -> list[dict]:
        xml_text = fetch_text(self.url)
        root = ET.fromstring(xml_text)
        items: list[ET.Element] = []
        if root.tag.endswith("rss"):
            items = list(root.findall(".//item"))
        else:
            items = list(root.findall(".//{*}entry"))

        results: list[dict] = []
        for item in items:
            title = (item.findtext("title") or item.findtext("{*}title") or "").strip()
            summary = (
                item.findtext("description")
                or item.findtext("{*}summary")
                or item.findtext("{*}content")
                or ""
            )
            link = item.findtext("link") or item.findtext("{*}link") or ""
            if not link:
                link_el = item.find("{*}link")
                if link_el is not None:
                    link = link_el.attrib.get("href", "")
            link = urljoin(self.url, link) if link else None
            text_blob = f"{title}\n{summary}\n{link or ''}"
            socials = extract_social_links(text_blob)
            website_url = _first_url(text_blob, exclude_social=True) or link
            telegram_links = socials.get("telegram") or []
            x_links = socials.get("x") or []
            discord_links = socials.get("discord") or []
            results.append(
                {
                    "canonical_name": title or self.name,
                    "website_url": website_url,
                    "telegram_url": telegram_links[0] if telegram_links else None,
                    "x_url": x_links[0] if x_links else None,
                    "discord_url": discord_links[0] if discord_links else None,
                    "chain": self.chain,
                    "launch_source": self.name,
                    "source_type": "announcement",
                    "source_name": self.name,
                    "raw_text": summary,
                }
            )
        return results


class AtomFeedSource(RSSFeedSource):
    def collect(self) -> list[dict]:
        xml_text = fetch_text(self.url)
        root = ET.fromstring(xml_text)
        items = list(root.findall(".//{*}entry"))

        results: list[dict] = []
        for item in items:
            title = (item.findtext("{*}title") or item.findtext("title") or "").strip()
            summary = (
                item.findtext("{*}summary")
                or item.findtext("{*}content")
                or item.findtext("summary")
                or item.findtext("content")
                or ""
            )
            link = ""
            for link_el in item.findall("{*}link"):
                rel = (link_el.attrib.get("rel") or "alternate").lower()
                href = link_el.attrib.get("href", "")
                if rel == "alternate" and href:
                    link = href
                    break
                if not link and href:
                    link = href
            link = urljoin(self.url, link) if link else None
            text_blob = f"{title}\n{summary}\n{link or ''}"
            socials = extract_social_links(text_blob)
            website_url = _first_url(text_blob, exclude_social=True) or link
            telegram_links = socials.get("telegram") or []
            x_links = socials.get("x") or []
            discord_links = socials.get("discord") or []
            results.append(
                {
                    "canonical_name": title or self.name,
                    "website_url": website_url,
                    "telegram_url": telegram_links[0] if telegram_links else None,
                    "x_url": x_links[0] if x_links else None,
                    "discord_url": discord_links[0] if discord_links else None,
                    "chain": self.chain,
                    "launch_source": self.name,
                    "source_type": "announcement",
                    "source_name": self.name,
                    "raw_text": summary,
                }
            )
        return results


class _ListingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[dict] = []
        self._current: dict | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {k.lower(): v for k, v in attrs if v is not None}
        if tag.lower() in {"article", "li", "div"} and attrs_map.get("data-project"):
            self._current = {
                "canonical_name": attrs_map.get("data-name") or attrs_map["data-project"],
                "website_url": attrs_map.get("data-website"),
                "telegram_url": attrs_map.get("data-telegram"),
                "x_url": attrs_map.get("data-x"),
                "discord_url": attrs_map.get("data-discord"),
            }

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"article", "li", "div"} and self._current:
            self.items.append(self._current)
            self._current = None


class HTMLListingSource(DiscoverySource):
    def __init__(self, name: str, url: str, chain: str) -> None:
        self.name = name
        self.url = url
        self.chain = chain

    def collect(self) -> list[dict]:
        html = fetch_text(self.url)
        parser = _ListingParser()
        parser.feed(html)
        return [
            dict(
                item,
                chain=item.get("chain", self.chain),
                launch_source=self.name,
                source_type="launchpad",
                source_name=self.name,
            )
            for item in parser.items
        ]


class PublicProfileSource(DiscoverySource):
    def __init__(self, name: str, url: str, chain: str) -> None:
        self.name = name
        self.url = url
        self.chain = chain

    def collect(self) -> list[dict]:
        html = fetch_text(self.url)
        parsed = extract_links(html, base_url=self.url)
        socials = {
            "telegram": parsed.get("telegram_links") or [],
            "x": parsed.get("x_links") or [],
            "discord": parsed.get("discord_links") or [],
        }
        website_links = [link for link in parsed.get("links") or [] if link and not any(host in link.lower() for host in ("t.me/", "telegram.me/", "x.com/", "twitter.com/", "discord.gg/", "discord.com/"))]

        if not website_links and not socials["telegram"] and not socials["x"] and not socials["discord"]:
            return []

        return [
            {
                "canonical_name": parsed.get("title") or self.name,
                "website_url": website_links[0] if website_links else None,
                "telegram_url": socials["telegram"][0] if socials["telegram"] else None,
                "x_url": socials["x"][0] if socials["x"] else None,
                "discord_url": socials["discord"][0] if socials["discord"] else None,
                "chain": self.chain,
                "launch_source": self.name,
                "source_type": "social",
                "source_name": self.name,
                "raw_text": parsed.get("meta_description") or parsed.get("title") or "",
            }
        ]


def _slug_to_name(value: str) -> str:
    cleaned = unquote(value.strip().rstrip("/"))
    if not cleaned:
        return "Unknown Project"
    slug = cleaned.split("/")[-1]
    slug = re.sub(r"[-_]+", " ", slug).strip()
    slug = re.sub(r"\s+", " ", slug)
    return slug.title() if slug else "Unknown Project"


class SitemapSource(DiscoverySource):
    def __init__(self, name: str, url: str, chain: str, max_pages: int = 25) -> None:
        self.name = name
        self.url = url
        self.chain = chain
        self.max_pages = max_pages

    def _site_root(self) -> str:
        parsed = urlparse(self.url)
        if parsed.path.endswith(".xml") or parsed.path.endswith("robots.txt"):
            return f"{parsed.scheme}://{parsed.netloc}"
        return self.url.rstrip("/")

    def _candidate_sitemap_urls(self) -> list[str]:
        candidates: list[str] = []
        if self.url.endswith(".xml"):
            candidates.append(self.url)
        root = self._site_root()
        robots_url = urljoin(root.rstrip("/") + "/", "robots.txt")
        candidates.append(robots_url)
        candidates.append(urljoin(root.rstrip("/") + "/", "sitemap.xml"))
        candidates.append(urljoin(root.rstrip("/") + "/", "sitemap_index.xml"))
        return list(dict.fromkeys(candidates))

    def _extract_sitemap_urls_from_robots(self, robots_text: str) -> list[str]:
        return [match.strip() for match in SITEMAP_DIRECTIVE_RE.findall(robots_text) if match.strip()]

    def _iter_page_urls(self) -> list[str]:
        sitemap_urls: list[str] = []
        for candidate in self._candidate_sitemap_urls():
            try:
                text = fetch_text(candidate)
            except Exception:
                continue
            if candidate.endswith("robots.txt"):
                sitemap_urls.extend(self._extract_sitemap_urls_from_robots(text))
                continue
            sitemap_urls.append(candidate)

        page_urls: list[str] = []
        for sitemap_url in sitemap_urls or [self.url]:
            try:
                xml_text = fetch_text(sitemap_url)
            except Exception:
                continue
            root = ET.fromstring(xml_text)
            locs = [loc.text.strip() for loc in root.findall(".//{*}loc") if loc.text and loc.text.strip()]
            if root.tag.endswith("sitemapindex"):
                for nested_sitemap_url in locs:
                    try:
                        nested_text = fetch_text(nested_sitemap_url)
                        nested_root = ET.fromstring(nested_text)
                        for loc in nested_root.findall(".//{*}loc"):
                            if loc.text and loc.text.strip():
                                page_urls.append(loc.text.strip())
                    except Exception:
                        continue
            else:
                page_urls.extend(locs)
        return page_urls[: self.max_pages]

    def collect(self) -> list[dict]:
        results: list[dict] = []
        for page_url in self._iter_page_urls():
            try:
                html = fetch_text(page_url)
            except Exception:
                continue
            parsed = extract_links(html, base_url=page_url)
            telegram_links = parsed.get("telegram_links") or []
            x_links = parsed.get("x_links") or []
            discord_links = parsed.get("discord_links") or []
            if not telegram_links and not x_links and not discord_links:
                continue
            title = parsed.get("title") or _slug_to_name(urlparse(page_url).path)
            results.append(
                {
                    "canonical_name": title,
                    "website_url": page_url,
                    "telegram_url": telegram_links[0] if telegram_links else None,
                    "x_url": x_links[0] if x_links else None,
                    "discord_url": discord_links[0] if discord_links else None,
                    "chain": self.chain,
                    "launch_source": self.name,
                    "source_type": "launchpad",
                    "source_name": self.name,
                    "raw_text": parsed.get("meta_description") or parsed.get("title") or "",
                }
            )
        return results
