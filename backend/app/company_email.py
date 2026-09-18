"""Resolve a company inbox for purchase notices and catalog supplier emails."""
from __future__ import annotations

from sqlalchemy import select

from .extensions import db
from .models.company import Company, Contact


def company_order_email(company: Company | None, *, load_contacts: bool = True) -> str | None:
    """Company email, else primary (then any) contact with an address."""
    if company is None or getattr(company, "deleted_at", None) is not None:
        return None
    inbox = (company.email or "").strip()
    if inbox:
        return inbox
    if not load_contacts:
        return None
    rows = db.session.scalars(
        select(Contact)
        .where(Contact.company_id == company.id, Contact.email.is_not(None))
        .order_by(Contact.is_primary.desc(), Contact.created_at)
    ).all()
    for row in rows:
        email = (row.email or "").strip()
        if email:
            return email
    return None
