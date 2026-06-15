from __future__ import annotations

import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.deployment import deployment_check_urls
from app.core.tunnel import extract_tunnel_url


def main() -> int:
    for line in sys.stdin:
        tunnel_url = extract_tunnel_url(line)
        if not tunnel_url:
            continue

        print(f"Tunnel URL found: {tunnel_url}")
        failures: list[str] = []
        for url in deployment_check_urls(tunnel_url):
            try:
                with urlopen(url, timeout=15) as response:
                    status = getattr(response, "status", 200)
                    print(f"OK {status} {url}")
            except URLError as exc:
                failures.append(f"{url}: {exc}")
                print(f"FAIL {url}: {exc}", file=sys.stderr)

        if failures:
            return 1

        print(f"Deployment is healthy at {tunnel_url}")
        print(f"Dashboard: {tunnel_url.rstrip('/')}/dashboard")
        return 0

    print("No Cloudflare Tunnel URL found in logs.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
