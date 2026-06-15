from __future__ import annotations

import re
from pathlib import Path
from tempfile import gettempdir
from urllib.parse import urlparse

from app.services.extractor import extract_links, fetch_url, hash_text

try:  # pragma: no cover - optional dependency
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - optional dependency
    sync_playwright = None  # type: ignore[assignment]


def render_website(url: str, screenshot_dir: str | None = None, timeout: int = 15000) -> dict[str, object] | None:
    if sync_playwright is None:
        return None

    target_dir = Path(screenshot_dir or Path(gettempdir()) / "marshallbot_screenshots")
    target_dir.mkdir(parents=True, exist_ok=True)
    parsed = urlparse(url)
    screenshot_path = target_dir / f"{parsed.netloc or 'site'}-{re.sub(r'[^a-zA-Z0-9]+', '-', parsed.path.strip('/'))[:40] or 'home'}.png"

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1600})
            page.goto(url, wait_until="networkidle", timeout=timeout)
            html = page.content()
            title = page.title()
            page.screenshot(path=str(screenshot_path), full_page=True)
            browser.close()
            return {
                "html": html,
                "title": title,
                "screenshot_path": str(screenshot_path),
            }
    except Exception:
        return None


def enrich_website(url: str) -> dict:
    html, metadata = fetch_url(url)
    rendered = render_website(url)
    rendered_html = rendered.get("html") if rendered else None
    rendered_title = rendered.get("title") if rendered else None
    parsed = extract_links(html, base_url=url)
    if rendered_html:
        rendered_parsed = extract_links(str(rendered_html), base_url=url)
        if rendered_parsed.get("telegram_links"):
            parsed["telegram_links"] = rendered_parsed.get("telegram_links", [])
        if rendered_parsed.get("x_links"):
            parsed["x_links"] = rendered_parsed.get("x_links", [])
        if rendered_parsed.get("discord_links"):
            parsed["discord_links"] = rendered_parsed.get("discord_links", [])
        if rendered_parsed.get("links"):
            parsed["links"] = rendered_parsed.get("links", [])
        if rendered_parsed.get("title"):
            parsed["title"] = rendered_parsed.get("title")
        if rendered_parsed.get("meta_description"):
            parsed["meta_description"] = rendered_parsed.get("meta_description")
    if rendered_title:
        parsed["title"] = rendered_title
    text_blob = re.sub(r"<[^>]+>", " ", html)
    words = [word for word in re.split(r"\s+", text_blob) if word.strip()]
    return {
        "url": url,
        "html_hash": hash_text(html),
        "text_hash": hash_text(" ".join(parsed.get("links", []))),
        "title": parsed.get("title"),
        "meta_description": parsed.get("meta_description"),
        "content_length": len(html),
        "word_count": len(words),
        "screenshot_path": rendered.get("screenshot_path") if rendered else None,
        "parsed_data": {
            "metadata": metadata,
            "links": parsed.get("links", []),
            "telegram_links": parsed.get("telegram_links", []),
            "x_links": parsed.get("x_links", []),
            "discord_links": parsed.get("discord_links", []),
            "content_length": len(html),
            "word_count": len(words),
            "rendered": bool(rendered),
        },
    }


def website_snapshot_from_enrichment(enrichment: dict) -> dict:
    return {
        "url": enrichment.get("url"),
        "title": enrichment.get("title"),
        "meta_description": enrichment.get("meta_description"),
        "html_hash": enrichment.get("html_hash"),
        "text_hash": enrichment.get("text_hash"),
        "parsed_data": enrichment.get("parsed_data", {}),
    }


def _chain_terms(chain: str | None) -> tuple[str, ...]:
    if chain == "bsc":
        return ("bnb", "bsc", "pancake", "pancakeswap", "four.meme", "bscscan")
    if chain == "solana":
        return ("sol", "solana", "solscan", "jupiter", "raydium", "pump.fun")
    return ()


def website_quality_score(parsed_data: dict, chain: str | None = None) -> float:
    score = 0.0
    combined_text = " ".join(
        [
            str(parsed_data.get("title", "")),
            str(parsed_data.get("meta_description", "")),
            " ".join(str(link) for link in parsed_data.get("links", [])),
        ]
    ).lower()
    if parsed_data.get("title"):
        score += 20
    if parsed_data.get("meta_description"):
        score += 15
    if parsed_data.get("telegram_links"):
        score += 20
    if parsed_data.get("x_links"):
        score += 10
    if parsed_data.get("discord_links"):
        score += 10
    if len(parsed_data.get("links", [])) >= 3:
        score += 15
    if len(parsed_data.get("links", [])) >= 6:
        score += 10
    if parsed_data.get("word_count", 0) >= 40:
        score += 10
    if parsed_data.get("content_length", 0) >= 1200:
        score += 10
    if parsed_data.get("content_length", 0) < 300:
        score -= 10
    if any(term in combined_text for term in ("roadmap", "tokenomics", "docs", "whitepaper")):
        score += 10
    if any(term in combined_text for term in ("buy", "trade", "chart", "community")):
        score += 5

    chain_terms = _chain_terms(chain)
    if chain_terms and any(term in combined_text for term in chain_terms):
        score += 10

    if chain == "bsc" and any(term in combined_text for term in ("pancakeswap", "bnb", "bscscan")):
        score += 5
    if chain == "solana" and any(term in combined_text for term in ("jupiter", "raydium", "solscan")):
        score += 5
    return min(100.0, score)
