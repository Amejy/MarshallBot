from __future__ import annotations

import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.deployment import deployment_check_urls
from app.core.tunnel import extract_tunnel_url


def main() -> int:
    local_base_url = "http://127.0.0.1:8000"
    local_failures: list[str] = []
    for url in deployment_check_urls(local_base_url):
        try:
            with urlopen(url, timeout=15) as response:
                status = getattr(response, "status", 200)
                print(f"OK {status} {url}")
        except URLError as exc:
            local_failures.append(f"{url}: {exc}")
            print(f"FAIL {url}: {exc}", file=sys.stderr)

    if local_failures:
        return 1

    for line in sys.stdin:
        tunnel_url = extract_tunnel_url(line)
        if not tunnel_url:
            continue

        print(f"Tunnel URL found: {tunnel_url}")
        print(f"Deployment is healthy at {tunnel_url}")
        print(f"Dashboard: {tunnel_url.rstrip('/')}/dashboard")
        return 0

    print("No Cloudflare Tunnel URL found in logs.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
