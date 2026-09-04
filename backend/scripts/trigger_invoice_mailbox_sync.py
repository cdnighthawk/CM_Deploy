"""Render cron: ask the live website to ingest invoices@ mail.

POSTs /api/v1/ap/mailbox/sync with X-Cron-Secret.

Env:
  BC_SYNC_CRON_SECRET           required (same secret as BuildingConnected / calendar)
  INVOICE_MAILBOX_SYNC_URL      optional, default
                                https://www.usiscm.com/api/v1/ap/mailbox/sync
"""
from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "https://www.usiscm.com/api/v1/ap/mailbox/sync"


def main() -> int:
    secret = (os.environ.get("BC_SYNC_CRON_SECRET") or "").strip()
    if not secret:
        print("BC_SYNC_CRON_SECRET is required", file=sys.stderr)
        return 1
    url = (os.environ.get("INVOICE_MAILBOX_SYNC_URL") or DEFAULT_URL).strip()
    req = urllib.request.Request(
        url,
        method="POST",
        headers={
            "Accept": "application/json",
            "X-Cron-Secret": secret,
            "User-Agent": "USIS-invoice-mailbox-sync/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=170) as resp:
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
