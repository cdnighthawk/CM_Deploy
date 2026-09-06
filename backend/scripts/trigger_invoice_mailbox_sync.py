"""Render cron: ask the live website to ingest invoices@ mail.

POSTs /api/v1/ap/mailbox/sync with X-Cron-Secret.

Env:
  BC_SYNC_CRON_SECRET           required (copied from usis-cm)
  USIS_WEB_HOSTPORT             optional, Render private host:port for usis-cm
  INVOICE_MAILBOX_SYNC_URL      optional public fallback
                                https://www.usiscm.com/api/v1/ap/mailbox/sync
"""
from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "https://www.usiscm.com/api/v1/ap/mailbox/sync"


def resolve_urls() -> list[str]:
    """Prefer Render private networking, then the public site."""
    urls: list[str] = []
    hostport = (os.environ.get("USIS_WEB_HOSTPORT") or "").strip()
    if hostport:
        urls.append(f"http://{hostport}/api/v1/ap/mailbox/sync")
    explicit = (os.environ.get("INVOICE_MAILBOX_SYNC_URL") or "").strip()
    if explicit and explicit not in urls:
        urls.append(explicit)
    if DEFAULT_URL not in urls:
        urls.append(DEFAULT_URL)
    return urls


def post_sync(url: str, secret: str, timeout: float = 170) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        data=b"{}",
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Cron-Secret": secret,
            "User-Agent": "USIS-invoice-mailbox-sync/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return int(resp.status), body


def main() -> int:
    secret = (os.environ.get("BC_SYNC_CRON_SECRET") or "").strip()
    if not secret:
        print(
            "BC_SYNC_CRON_SECRET is required. Copy it from the usis-cm web service "
            "or sync the Blueprint so this cron inherits that value.",
            file=sys.stderr,
        )
        return 1
    last_network_error = ""
    for url in resolve_urls():
        try:
            status, body = post_sync(url, secret)
            print(status, body)
            return 0
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            print(exc.code, body, file=sys.stderr)
            if exc.code == 401:
                print(
                    "Cron secret was rejected. Confirm BC_SYNC_CRON_SECRET on this "
                    "job matches the usis-cm web service.",
                    file=sys.stderr,
                )
            return 1
        except Exception as exc:
            last_network_error = f"{url}: {exc}"
            print(last_network_error, file=sys.stderr)
            continue
    if last_network_error:
        return 1
    print("no mailbox sync URL configured", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
