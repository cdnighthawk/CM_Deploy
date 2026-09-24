"""Background poll of correspondence mailboxes so USIS-REF mail files without a button click."""
from __future__ import annotations

import os
import sys
import threading
import time

from flask import Flask

_STARTED = False
_START_LOCK = threading.Lock()


def start_correspondence_mailbox_sync_loop(app: Flask) -> None:
    """Poll Graph every ``CORRESPONDENCE_MAILBOX_SYNC_INTERVAL_SEC`` (default 300). Set 0 to disable."""
    global _STARTED
    if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
        return
    if os.environ.get("WERKZEUG_RUN_MAIN") == "false":
        return
    debug = bool(app.debug) or (os.environ.get("FLASK_DEBUG") or "").strip().lower() in ("1", "true", "yes")
    if debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return
    try:
        interval = int(app.config.get("CORRESPONDENCE_MAILBOX_SYNC_INTERVAL_SEC") or 300)
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
                    from ._correspondence_service import configured_mailboxes, sync_mailboxes
                    from ._notifications import _graph_configured
                    from ._rfi_service import ApiError
                    from ..extensions import db

                    if not _graph_configured() or not configured_mailboxes():
                        app.logger.debug("correspondence mailbox auto-sync skipped; Graph or mailbox unset")
                    else:
                        result = sync_mailboxes(cu=None)
                        db.session.commit()
                        if result.get("created") or result.get("errors"):
                            app.logger.info("correspondence mailbox auto-sync %s", result)
            except Exception as exc:
                try:
                    from ..extensions import db

                    db.session.rollback()
                except Exception:
                    pass
                from ._rfi_service import ApiError

                if isinstance(exc, ApiError):
                    app.logger.debug("correspondence mailbox auto-sync: %s", exc.message)
                else:
                    app.logger.exception("correspondence mailbox auto-sync failed")
            time.sleep(interval)

    threading.Thread(target=_run, name="correspondence-mailbox-sync", daemon=True).start()
    app.logger.info("Correspondence mailbox auto-sync every %s seconds", interval)
