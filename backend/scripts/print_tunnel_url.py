from __future__ import annotations

import sys

from app.core.tunnel import extract_tunnel_url


def main() -> int:
    for line in sys.stdin:
        url = extract_tunnel_url(line)
        if url:
            print(url)
            return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
