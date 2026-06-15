from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.tunnel import extract_tunnel_url


def main() -> int:
    for line in sys.stdin:
        url = extract_tunnel_url(line)
        if not url:
            continue

        dashboard_url = f"{url.rstrip('/')}/dashboard"
        print(dashboard_url)
        webbrowser.open(dashboard_url)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
