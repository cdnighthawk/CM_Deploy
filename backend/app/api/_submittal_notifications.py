"""Submittal QC emails — reuse SMTP/Celery dispatch, do not touch RFP templates."""
from __future__ import annotations

from typing import TYPE_CHECKING

from flask import render_template

from ._notifications import _dispatch

if TYPE_CHECKING:
    from ..models import Submittal
    from ._perms import CurrentUser


def enqueue_submittal_email(s: "Submittal", event: str, actor: "CurrentUser | None" = None) -> None:
    reviewer = s.assigned_reviewer
    to = (reviewer.email if reviewer else None) or (s.ball_in_court or "").strip()
    if "@" not in (to or ""):
        return
    number = s.submittal_number or f"#{s.number}"
    subjects = {
        "assigned": f"Submittal {number} assigned for QC",
        "due_48h": f"Submittal {number} due in 48 hours",
        "overdue": f"Submittal {number} is overdue",
        "rejected": f"Submittal {number} rejected / revise & resubmit",
        "stamped": f"Submittal {number} stamped ({s.status})",
        "transmitted": f"Submittal {number} transmitted to GC/AE",
    }
    subject = subjects.get(event, f"Submittal {number} update")
    try:
        body = render_template(
            "submittals/email.txt",
            submittal=s,
            event=event,
            number=number,
            actor_email=getattr(getattr(actor, "user", None), "email", None),
        )
    except Exception:
        body = f"{subject}\n\n{s.title}\nStatus: {s.status}\n"
    _dispatch(log_id="None", subject=subject, body=body, to=to)
