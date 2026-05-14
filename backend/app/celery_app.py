"""Optional Celery integration for the RFI tool.

When ``CELERY_BROKER_URL`` is set (e.g. ``redis://localhost:6379/0``),
``app.api._notifications`` will dispatch RFI emails as background tasks.
If Celery is not installed or the env var is missing the call site falls
back to inline send via ``smtplib``.

To run a worker:

::

    set CELERY_BROKER_URL=redis://localhost:6379/0
    celery -A app.celery_app:celery worker -l info

Adding more tasks (e.g. PDF rendering for "Email this RFI" attachments)
should land here.
"""
from __future__ import annotations

import os

try:
    from celery import Celery
except Exception:  # pragma: no cover — Celery is an optional dependency
    Celery = None  # type: ignore[assignment]


BROKER = os.environ.get("CELERY_BROKER_URL")
BACKEND = os.environ.get("CELERY_RESULT_BACKEND") or BROKER

celery = None  # type: ignore[assignment]

if Celery is not None and BROKER:
    celery = Celery("usis_cm", broker=BROKER, backend=BACKEND)
    celery.conf.task_default_queue = "rfi"
    celery.conf.task_routes = {"rfi.*": {"queue": "rfi"}}

    @celery.task(name="rfi.send_email")
    def send_rfi_email_task(*, log_id: str, subject: str, body: str, to: str) -> None:  # pragma: no cover
        """Send an RFI email out-of-band.

        On success/failure stamps the corresponding ``rfi_notification_log``
        row via ``app.api._notifications._mark_log_delivered``.
        """
        from . import create_app
        from .api._notifications import _mark_log_delivered, _send_via_smtplib, _smtp_configured
        from .extensions import db

        app = create_app()
        with app.app_context():
            try:
                if _smtp_configured():
                    _send_via_smtplib(subject=subject, body=body, to=to)
                _mark_log_delivered(log_id)
            except Exception as exc:
                _mark_log_delivered(log_id, error=str(exc))
                raise
            db.session.commit()
