from __future__ import annotations

import re

_TUNNEL_URL_PATTERN = re.compile(r"https://[A-Za-z0-9-]+\.trycloudflare\.com")


def extract_tunnel_url(line: str) -> str | None:
    match = _TUNNEL_URL_PATTERN.search(line)
    if match:
        return match.group(0)
    return None
