"""Daily Render cron: remind assignees the day before / morning a window starts.

POSTs /api/v1/integrations/calendar-reminders/run with X-Cron-Secret.

Env:
  BC_SYNC_CRON_SECRET          required (same secret as BuildingConnected hourly)
  CALENDAR_REMINDER_URL        optional, default
                               https://www.usiscm.com/api/v1/integrations/calendar-reminders/run
"""
from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "https://www.usiscm.com/api/v1/integrations/calendar-reminders/run"


def main() -> int:
    secret = (os.environ.get("BC_SYNC_CRON_SECRET") or "").strip()
    if not secret:
        print("BC_SYNC_CRON_SECRET is required", file=sys.stderr)
        return 1
    url = (os.environ.get("CALENDAR_REMINDER_URL") or DEFAULT_URL).strip()
    req = urllib.request.Request(
        url,
        method="POST",
        headers={
            "Accept": "application/json",
            "X-Cron-Secret": secret,
            "User-Agent": "USIS-calendar-reminders/1.0",
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
