"""Hourly Render cron: ask the live website to pull recent Bid Board updates.

The web service already holds the Autodesk refresh token. This script only
POSTs /api/v1/integrations/buildingconnected/sync with X-Cron-Secret.

Env:
  BC_SYNC_CRON_SECRET  required
  BC_SYNC_URL          optional, default https://www.usiscm.com/api/v1/integrations/buildingconnected/sync
"""
from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "https://www.usiscm.com/api/v1/integrations/buildingconnected/sync"


def main() -> int:
    secret = (os.environ.get("BC_SYNC_CRON_SECRET") or "").strip()
    if not secret:
        print("BC_SYNC_CRON_SECRET is required", file=sys.stderr)
        return 1
    url = (os.environ.get("BC_SYNC_URL") or DEFAULT_URL).strip()
    req = urllib.request.Request(
        url,
        method="POST",
        headers={
            "Accept": "application/json",
            "X-Cron-Secret": secret,
            "User-Agent": "USIS-BC-hourly/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            print(resp.status, body)
            return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(exc.code, body, file=sys.stderr)
        return 1
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
