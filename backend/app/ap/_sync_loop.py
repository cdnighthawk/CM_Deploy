"""Background poll of invoices@ so vendor mail is ingested without a button click."""
from __future__ import annotations

import os
import sys
import threading
import time

from flask import Flask

_STARTED = False
_START_LOCK = threading.Lock()


def start_invoice_mailbox_sync_loop(app: Flask) -> None:
    """Poll Graph every ``INVOICE_MAILBOX_SYNC_INTERVAL_SEC`` (default 300). Set 0 to disable."""
    global _STARTED
    if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
        return
    if os.environ.get("WERKZEUG_RUN_MAIN") == "false":
        return
    debug = bool(app.debug) or (os.environ.get("FLASK_DEBUG") or "").strip().lower() in ("1", "true", "yes")
    if debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return
    try:
        interval = int(app.config.get("INVOICE_MAILBOX_SYNC_INTERVAL_SEC") or 300)
    except (TypeError, ValueError):
        interval = 300
    if interval <= 0:
        return
    with _START_LOCK:
        if _STARTED:
            return
        _STARTED = True

    def _run() -> None:
        time.sleep(min(30, interval))
        while True:
            try:
                with app.app_context():
                    from ..extensions import db
                    from ._mailbox import mailbox_ready, sync_invoice_mailbox

                    if not mailbox_ready():
                        app.logger.debug("invoice mailbox auto-sync skipped; Graph is not configured")
                    else:
                        result = sync_invoice_mailbox(actor_user_id=None)
                        db.session.commit()
                        if result.get("created") or result.get("errors"):
                            app.logger.info("invoice mailbox auto-sync %s", result)
            except Exception:
                try:
                    from ..extensions import db

                    db.session.rollback()
                except Exception:
                    pass
                app.logger.exception("invoice mailbox auto-sync failed")
            time.sleep(interval)

    threading.Thread(target=_run, name="invoice-mailbox-sync", daemon=True).start()
    app.logger.info("Invoice mailbox auto-sync every %s seconds", interval)
