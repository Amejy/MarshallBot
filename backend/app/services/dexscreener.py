from __future__ import annotations

import re
from urllib.parse import quote

from app.services.connectors import fetch_json
from app.services.sources import DiscoverySource


DEXSCREENER_API_BASE = "https://api.dexscreener.com"
PROFILE_ENDPOINT = f"{DEXSCREENER_API_BASE}/token-profiles/latest/v1"
BOOST_ENDPOINT = f"{DEXSCREENER_API_BASE}/token-boosts/latest/v1"
PAIR_ENDPOINT = f"{DEXSCREENER_API_BASE}/token-pairs/v1"


def _slug_to_name(value: str) -> str:
    cleaned = value.strip().replace("-", " ").replace("_", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.title() if cleaned else "DexScreener Project"


def _normalize_text(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalize_link(url: str | None) -> str | None:
    text = _normalize_text(url)
    if not text:
        return None
    return text.rstrip(").,]}>")


def _extract_links_from_profile_links(profile: dict) -> dict[str, list[str]]:
    website_links: list[str] = []
    telegram_links: list[str] = []
    x_links: list[str] = []
    discord_links: list[str] = []

    for link in profile.get("links") or []:
        if not isinstance(link, dict):
            continue
        url = _normalize_link(link.get("url"))
        if not url:
            continue
        label = str(link.get("label") or link.get("type") or "").lower()
        if "telegram" in label or "t.me" in url.lower():
            telegram_links.append(url)
        elif "twitter" in label or label == "x" or "x.com" in url.lower():
            x_links.append(url)
        elif "discord" in label or "discord" in url.lower():
            discord_links.append(url)
        elif "website" in label or "site" in label or "homepage" in label:
            website_links.append(url)
        else:
            website_links.append(url)

    return {
        "website_links": list(dict.fromkeys(website_links)),
        "telegram_links": list(dict.fromkeys(telegram_links)),
        "x_links": list(dict.fromkeys(x_links)),
        "discord_links": list(dict.fromkeys(discord_links)),
    }


def _candidate_pairs(chain: str, token_address: str) -> list[dict]:
    url = f"{PAIR_ENDPOINT}/{quote(chain)}/{quote(token_address)}"
    payload = fetch_json(url)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        pairs = payload.get("pairs")
        if isinstance(pairs, list):
            return [item for item in pairs if isinstance(item, dict)]
    return []


def _best_pair(pairs: list[dict]) -> dict | None:
    if not pairs:
        return None

    def _score(pair: dict) -> tuple[float, float, float]:
        liquidity = pair.get("liquidity", {}) if isinstance(pair.get("liquidity"), dict) else {}
        volume = pair.get("volume", {}) if isinstance(pair.get("volume"), dict) else {}
        price = pair.get("priceUsd")
        liquidity_usd = float(liquidity.get("usd") or 0)
        volume_h24 = float(volume.get("h24") or 0)
        try:
            price_value = float(price or 0)
        except (TypeError, ValueError):
            price_value = 0.0
        return liquidity_usd, volume_h24, price_value

    return sorted(pairs, key=_score, reverse=True)[0]


class DexScreenerSource(DiscoverySource):
    def __init__(self, name: str, url: str, chain: str, limit: int = 25) -> None:
        self.name = name
        self.url = url
        self.chain = chain
        self.limit = limit

    def _token_profiles(self) -> list[dict]:
        payload = fetch_json(PROFILE_ENDPOINT)
        profiles = payload if isinstance(payload, list) else []
        return [item for item in profiles if isinstance(item, dict) and item.get("chainId") == self.chain and item.get("tokenAddress")]

    def _boosted_profiles(self) -> list[dict]:
        try:
            payload = fetch_json(BOOST_ENDPOINT)
        except Exception:
            return []
        boosted = payload if isinstance(payload, list) else payload.get("boosts") if isinstance(payload, dict) else []
        if not isinstance(boosted, list):
            return []
        return [item for item in boosted if isinstance(item, dict) and item.get("chainId") == self.chain and item.get("tokenAddress")]

    def _build_project(self, profile: dict) -> dict | None:
        token_address = str(profile.get("tokenAddress") or "").strip()
        if not token_address:
            return None

        pairs = _candidate_pairs(self.chain, token_address)
        pair = _best_pair(pairs)
        if not pair:
            return None

        base_token = pair.get("baseToken") if isinstance(pair.get("baseToken"), dict) else {}
        quote_token = pair.get("quoteToken") if isinstance(pair.get("quoteToken"), dict) else {}
        pair_url = _normalize_text(pair.get("url"))
        extra_links = _extract_links_from_profile_links(profile)
        websites = extra_links["website_links"]
        telegram_links = extra_links["telegram_links"]
        x_links = extra_links["x_links"]
        discord_links = extra_links["discord_links"]

        socials = profile.get("links") or []
        if pair.get("info") and isinstance(pair["info"], dict):
            info_links = _extract_links_from_profile_links(pair["info"])
            websites = websites or info_links["website_links"]
            telegram_links = telegram_links or info_links["telegram_links"]
            x_links = x_links or info_links["x_links"]
            discord_links = discord_links or info_links["discord_links"]

        name = _normalize_text(base_token.get("name")) or _normalize_text(profile.get("description"))
        symbol = _normalize_text(base_token.get("symbol"))
        canonical_name = name or (f"{symbol} ({self.chain})" if symbol else None) or _slug_to_name(token_address[:10])

        liquidity = pair.get("liquidity") if isinstance(pair.get("liquidity"), dict) else {}
        volume = pair.get("volume") if isinstance(pair.get("volume"), dict) else {}

        return {
            "canonical_name": canonical_name,
            "chain": self.chain,
            "website_url": websites[0] if websites else _normalize_link(profile.get("url")),
            "telegram_url": telegram_links[0] if telegram_links else None,
            "x_url": x_links[0] if x_links else None,
            "discord_url": discord_links[0] if discord_links else None,
            "launch_source": self.name,
            "source_type": "launchpad",
            "source_name": self.name,
            "dexscreener_url": pair_url,
            "token_address": token_address,
            "pair_address": _normalize_text(pair.get("pairAddress")),
            "base_token_symbol": _normalize_text(base_token.get("symbol")),
            "base_token_name": _normalize_text(base_token.get("name")),
            "quote_token_symbol": _normalize_text(quote_token.get("symbol")),
            "quote_token_name": _normalize_text(quote_token.get("name")),
            "liquidity_usd": liquidity.get("usd"),
            "liquidity_base": liquidity.get("base"),
            "liquidity_quote": liquidity.get("quote"),
            "volume_24h": volume.get("h24"),
            "fdv": pair.get("fdv"),
            "market_cap": pair.get("marketCap"),
            "price_usd": pair.get("priceUsd"),
            "pair_created_at": pair.get("pairCreatedAt"),
            "profile_url": _normalize_text(profile.get("url")),
            "profile_description": _normalize_text(profile.get("description")),
            "raw_text": _normalize_text(profile.get("description")) or _normalize_text(profile.get("label")) or "",
            "dexscreener_profile": profile,
            "dexscreener_pair": pair,
            "dexscreener_socials": socials,
        }

    def collect(self) -> list[dict]:
        seen: set[str] = set()
        projects: list[dict] = []

        for profile in self._boosted_profiles() + self._token_profiles():
            token_address = str(profile.get("tokenAddress") or "").strip()
            if not token_address or token_address in seen:
                continue
            seen.add(token_address)
            try:
                project = self._build_project(profile)
            except Exception:
                continue
            if project:
                projects.append(project)
            if len(projects) >= self.limit:
                break

        return projects
