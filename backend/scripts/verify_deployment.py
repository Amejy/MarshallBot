from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.deployment import deployment_check_urls


def main() -> int:
    base_url = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.environ.get("BASE_URL")
        or os.environ.get("MARSHALLBOT_BASE_URL")
        or "http://127.0.0.1:8000"
    )

    failures: list[str] = []
    for url in deployment_check_urls(base_url):
        try:
            with urlopen(url, timeout=15) as response:
                status = getattr(response, "status", 200)
                print(f"OK {status} {url}")
        except URLError as exc:
            failures.append(f"{url}: {exc}")
            print(f"FAIL {url}: {exc}", file=sys.stderr)

    if failures:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
