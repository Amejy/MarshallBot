import hashlib
import re
from urllib.parse import urlparse


def normalize_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "", name).lower()
    return cleaned


def normalize_domain(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def normalize_contact_identifier(value: str | None) -> str | None:
    if not value:
        return None

    text = value.strip()
    if not text:
        return None

    if text.startswith("@"):
        return text[1:].strip().lower() or None

    if "://" not in text and re.match(r"^[a-z0-9.-]+\.[a-z]{2,}(/|$)", text, re.IGNORECASE):
        text = f"https://{text}"

    parsed = urlparse(text)
    if parsed.scheme and parsed.netloc:
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        path = parsed.path.strip("/")
        if host in {"t.me", "telegram.me", "telegram.dog"}:
            if not path:
                return host
            return path.split("/", 1)[0].lstrip("@").lower()
        if host in {"x.com", "twitter.com"}:
            if not path:
                return host
            return path.split("/", 1)[0].lstrip("@").lower()
        if host in {"discord.gg", "discord.com"}:
            if not path:
                return host
            parts = [part for part in path.split("/") if part]
            if host == "discord.com" and parts[:1] == ["invite"] and len(parts) > 1:
                return parts[1].lstrip("@").lower()
            return parts[0].lstrip("@").lower()
        return host

    return text.lower()


def fingerprint(*parts: str) -> str:
    payload = "|".join(part.strip().lower() for part in parts if part)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
