from __future__ import annotations

import time
import sys
from pathlib import Path
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.deployment import deployment_check_urls
from app.core.tunnel import extract_tunnel_url


def _wait_for_local_api(base_url: str, timeout_seconds: int = 180, poll_seconds: int = 5) -> bool:
    deadline = time.monotonic() + timeout_seconds
    last_error: str | None = None

    while time.monotonic() < deadline:
        all_ok = True
        for url in deployment_check_urls(base_url):
            try:
                with urlopen(url, timeout=15) as response:
                    status = getattr(response, "status", 200)
                    print(f"OK {status} {url}")
            except Exception as exc:  # transient startup/network issues are normal here
                all_ok = False
                last_error = f"{url}: {exc}"
                print(f"WAIT {url}: {exc}", file=sys.stderr)
                break

        if all_ok:
            return True

        time.sleep(poll_seconds)

    if last_error:
        print(f"Local API did not become ready: {last_error}", file=sys.stderr)
    return False


def main() -> int:
    if not _wait_for_local_api("http://127.0.0.1:8000"):
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
