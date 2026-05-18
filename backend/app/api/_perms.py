"""RFI permission helpers (Procore-style matrix).

Procore exposes a 3-tier RBAC for each project tool — ``None`` /
``Read-Only`` / ``Standard`` / ``Admin`` — plus granular toggles such as
*Act as RFI Manager* and *Mark Official Responses*. This module distills
that matrix down to the few decisions actually consulted by the API:

- ``can_view_rfi``        — is this user allowed to read the RFI?
- ``can_create_rfi``      — can they POST /projects/<pid>/rfis?
- ``can_create_open_rfi`` — can they create one directly as ``open`` (vs.
                            ``draft``)?
- ``can_edit_rfi``        — can they PATCH the RFI in its current status?
- ``can_act_as_manager``  — can they perform RFI Manager actions on this
                            RFI (close, reopen, ball-in-court, official
                            response, edit-open)?
- ``can_mark_official``   — can they mark a reply as the Official Response
                            (a less-restrictive variant)?
- ``can_reply``           — can they post a reply?
- ``can_delete_rfi``      — soft-delete (move to recycle bin)?
- ``can_restore_rfi``     — restore from recycle bin?

The current ``backend.app.models.auth`` scaffolding stores roles by code
on the ``roles`` table joined to users via ``user_roles``. Real auth
(sessions / JWT) is *not yet wired into the API blueprint*, so this
module also exposes a ``current_user`` helper that reads
``X-Usis-User-Id`` / ``?as_user=<uuid>`` for local development and the
forthcoming session middleware.

Permission policy (mirrors Procore's published matrix):

============================================ ====== ====== ======== =====
Action                                       None   Read   Standard Admin
============================================ ====== ====== ======== =====
View RFI                                            x      x        x
View Private RFI (same company)                     *      *        x
Create Draft                                              x         x
Create Open                                               x*        x
Edit Draft (own)                                          x         x
Edit Open                                                 x*        x
Reply to RFI (Assignee/Manager)                           x*        x
Mark Official Response                                    x*        x
Close / Reopen / Shift Ball-in-Court                      x*        x
Delete (recycle bin)                                                x

Cells marked ``x*`` additionally require *Act as RFI Manager* or being
designated as the manager / creator / current ball-in-court — Procore's
"granular permission" model.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable, Optional

from flask import g, has_request_context, request, session
from sqlalchemy import select

from ..extensions import db
from ..models import User

if TYPE_CHECKING:
    from ..models import Rfi


# ---------------------------------------------------------------------------
# User resolution
# ---------------------------------------------------------------------------


@dataclass
class CurrentUser:
    user: Optional[User]
    role_codes: frozenset[str]
    granular: frozenset[str]
    is_dev_admin: bool = False
    module_access: Optional[dict[str, str]] = None

    @property
    def id(self) -> Optional[uuid.UUID]:
        return self.user.id if self.user else None

    def has_role(self, *codes: str) -> bool:
        return any(c in self.role_codes for c in codes)

    def has_granular(self, *codes: str) -> bool:
        return any(c in self.granular for c in codes)


def _dev_unrestricted() -> bool:
    """Anonymous admin-style API access for local tooling.

    **Default is off:** callers must sign in (session or ``X-Usis-User-Id``) unless
    ``USIS_API_DEV_ALLOW_ANY`` is set to a truthy value (``1``, ``true``, …).
    """

    raw = os.environ.get("USIS_API_DEV_ALLOW_ANY")
    if raw is None:
        return False
    return raw.strip().lower() not in ("0", "false", "no", "off", "")


def allow_dev_anonymous_access() -> bool:
    """Public alias for guards that skip session when dev-open mode is enabled."""
    return _dev_unrestricted()


def _parse_uuid(raw: Optional[str]) -> Optional[uuid.UUID]:
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _role_codes_for(user: User) -> frozenset[str]:
    codes: set[str] = set()
    if user.is_superuser:
        codes.add("admin")
    for ur in user.roles or ():
        if ur.role is not None and ur.role.code:
            codes.add(ur.role.code)
    return frozenset(codes)


def _module_access_for(user: User) -> dict[str, str]:
    from ..permissions.access import effective_permissions_for_user

    return effective_permissions_for_user(user)


def _granular_for(user: User) -> frozenset[str]:
    """Granular permission codes are stored in ``users.tags`` JSON for now
    (free-form). When the full RBAC system lands this resolves against
    ``permissions_templates``.  Today an Admin / Superuser implicitly has
    every granular permission."""
    if user.is_superuser:
        return frozenset({"act_as_rfi_manager", "mark_official_responses"})
    return frozenset()


def current_user() -> CurrentUser:
    """Resolve the calling user for permission decisions.

    Order of resolution:

    1. ``flask.g.current_user`` set by an upstream auth middleware.
    2. ``Authorization: Bearer`` mobile access JWT.
    3. Request header ``X-Usis-User-Id`` (UUID) — overrides session for dev / impersonation.
    4. Query param ``?as_user=<uuid>`` (UUID).
    5. Signed-in browser session ``session['user_id']`` (see ``/auth/login``).
    6. ``USIS_DEV_ACTOR_USER_ID`` env var.
    7. ``USIS_API_DEV_ALLOW_ANY`` explicitly truthy (``1`` / ``true``) → synthetic admin for
       tooling; otherwise anonymous requests are unauthenticated.
    """

    if has_request_context():
        existing = getattr(g, "current_user", None)
        if isinstance(existing, CurrentUser):
            return existing

        from ._auth_mobile import bearer_user_from_request

        bearer_u = bearer_user_from_request()
        if bearer_u is not None:
            cu = CurrentUser(
                user=bearer_u,
                role_codes=_role_codes_for(bearer_u),
                granular=_granular_for(bearer_u),
                module_access=_module_access_for(bearer_u),
            )
            g.current_user = cu
            return cu

        for source in (
            request.headers.get("X-Usis-User-Id"),
            request.args.get("as_user"),
        ):
            uid = _parse_uuid(source)
            if uid is not None:
                u = db.session.get(User, uid)
                if u is not None:
                    cu = CurrentUser(
                        user=u,
                        role_codes=_role_codes_for(u),
                        granular=_granular_for(u),
                        module_access=_module_access_for(u),
                    )
                    g.current_user = cu
                    return cu

        sess_raw = session.get("user_id")
        sess_uid = _parse_uuid(str(sess_raw).strip() if sess_raw is not None else None)
        if sess_uid is not None:
            u = db.session.get(User, sess_uid)
            if u is not None and getattr(u, "is_active", True):
                cu = CurrentUser(
                    user=u,
                    role_codes=_role_codes_for(u),
                    granular=_granular_for(u),
                    module_access=_module_access_for(u),
                )
                g.current_user = cu
                return cu
            session.pop("user_id", None)

    env_uid = _parse_uuid(os.environ.get("USIS_DEV_ACTOR_USER_ID"))
    if env_uid is not None:
        u = db.session.get(User, env_uid)
        if u is not None:
            cu = CurrentUser(
                user=u,
                role_codes=_role_codes_for(u),
                granular=_granular_for(u),
                module_access=_module_access_for(u),
            )
            if has_request_context():
                g.current_user = cu
            return cu

    if _dev_unrestricted():
        from ..permissions.access import all_admin_permissions

        cu = CurrentUser(
            user=None,
            role_codes=frozenset({"admin"}),
            granular=frozenset({"act_as_rfi_manager", "mark_official_responses"}),
            is_dev_admin=True,
            module_access=all_admin_permissions(),
        )
        if has_request_context():
            g.current_user = cu
        return cu

    cu = CurrentUser(user=None, role_codes=frozenset(), granular=frozenset())
    if has_request_context():
        g.current_user = cu
    return cu


# ---------------------------------------------------------------------------
# RFI permission predicates
# ---------------------------------------------------------------------------


def _is_admin(cu: CurrentUser) -> bool:
    return cu.is_dev_admin or cu.has_role("admin", "superuser")


def can_manage_directory_users(cu: CurrentUser) -> bool:
    """Whether the caller may use admin user/role directory APIs (list/edit users, assign roles)."""
    if _is_admin(cu):
        return True
    from ..permissions.access import has_module_access

    return has_module_access(cu, "user_admin", "admin")


def _is_standard(cu: CurrentUser) -> bool:
    return cu.has_role("standard") or _is_admin(cu)


def _is_read_only(cu: CurrentUser) -> bool:
    return cu.has_role("read_only", "readonly") or _is_standard(cu)


def _is_creator(cu: CurrentUser, rfi: "Rfi") -> bool:
    return bool(cu.id and rfi.created_by_user_id and cu.id == rfi.created_by_user_id)


def _is_manager(cu: CurrentUser, rfi: "Rfi") -> bool:
    return bool(cu.id and rfi.rfi_manager_user_id and cu.id == rfi.rfi_manager_user_id)


def _is_assignee(cu: CurrentUser, rfi: "Rfi") -> bool:
    if cu.id is None:
        return False
    return any(a.user_id == cu.id for a in rfi.assignees)


def _is_ball_in_court(cu: CurrentUser, rfi: "Rfi") -> bool:
    if cu.id is None:
        return False
    return any(a.user_id == cu.id and a.ball_in_court for a in rfi.assignees)


def _is_distribution_member(cu: CurrentUser, rfi: "Rfi") -> bool:
    if cu.id is None:
        return False
    return any(d.user_id == cu.id for d in rfi.distribution)


def can_view_rfi(cu: CurrentUser, rfi: "Rfi") -> bool:
    if _is_admin(cu):
        return True
    if rfi.is_deleted and not _is_admin(cu):
        return False
    if not rfi.is_private:
        return _is_read_only(cu) or _is_creator(cu, rfi) or _is_assignee(cu, rfi) or _is_distribution_member(cu, rfi)
    return _is_creator(cu, rfi) or _is_manager(cu, rfi) or _is_assignee(cu, rfi) or _is_distribution_member(cu, rfi)


def can_create_rfi(cu: CurrentUser) -> bool:
    return _is_standard(cu) or _is_admin(cu)


def can_create_open_rfi(cu: CurrentUser) -> bool:
    if _is_admin(cu):
        return True
    return _is_standard(cu) and cu.has_granular("act_as_rfi_manager")


def can_act_as_manager(cu: CurrentUser, rfi: "Rfi") -> bool:
    if _is_admin(cu):
        return True
    if not cu.has_granular("act_as_rfi_manager"):
        return False
    return _is_manager(cu, rfi) or _is_creator(cu, rfi)


def can_mark_official(cu: CurrentUser, rfi: "Rfi") -> bool:
    if can_act_as_manager(cu, rfi):
        return True
    if cu.has_granular("mark_official_responses"):
        return _is_creator(cu, rfi) or _is_assignee(cu, rfi) or _is_distribution_member(cu, rfi)
    return False


def can_edit_rfi(cu: CurrentUser, rfi: "Rfi") -> bool:
    if _is_admin(cu):
        return True
    if rfi.status == "draft":
        return _is_creator(cu, rfi) or can_act_as_manager(cu, rfi)
    return can_act_as_manager(cu, rfi)


def can_reply(cu: CurrentUser, rfi: "Rfi") -> bool:
    if _is_admin(cu):
        return True
    if not _is_read_only(cu):
        return False
    return (
        _is_assignee(cu, rfi)
        or _is_manager(cu, rfi)
        or _is_creator(cu, rfi)
        or _is_distribution_member(cu, rfi)
    )


def can_close_or_reopen(cu: CurrentUser, rfi: "Rfi") -> bool:
    return can_act_as_manager(cu, rfi)


def can_shift_ball_in_court(cu: CurrentUser, rfi: "Rfi") -> bool:
    return can_act_as_manager(cu, rfi) or _is_ball_in_court(cu, rfi)


def can_add_assignee(cu: CurrentUser, rfi: "Rfi") -> bool:
    return can_act_as_manager(cu, rfi) or _is_ball_in_court(cu, rfi)


def can_forward(cu: CurrentUser, rfi: "Rfi") -> bool:
    return _is_ball_in_court(cu, rfi) or can_act_as_manager(cu, rfi)


def can_delete_rfi(cu: CurrentUser, rfi: "Rfi") -> bool:
    return _is_admin(cu) or (can_act_as_manager(cu, rfi))


def can_restore_rfi(cu: CurrentUser, rfi: "Rfi") -> bool:
    return _is_admin(cu)


def can_manage_saved_view_scope(cu: CurrentUser, scope: str) -> bool:
    if scope == "user":
        return cu.id is not None or cu.is_dev_admin
    if scope == "project":
        return _is_standard(cu) or _is_admin(cu)
    if scope == "company":
        return _is_admin(cu)
    return False


# ---------------------------------------------------------------------------
# Reasoning helpers
# ---------------------------------------------------------------------------


def explain_rfi(cu: CurrentUser, rfi: "Rfi") -> dict[str, bool]:
    """Snapshot every can_* answer for the UI to drive button enablement."""
    return {
        "can_view": can_view_rfi(cu, rfi),
        "can_edit": can_edit_rfi(cu, rfi),
        "can_reply": can_reply(cu, rfi),
        "can_act_as_manager": can_act_as_manager(cu, rfi),
        "can_mark_official": can_mark_official(cu, rfi),
        "can_close_or_reopen": can_close_or_reopen(cu, rfi),
        "can_shift_ball_in_court": can_shift_ball_in_court(cu, rfi),
        "can_add_assignee": can_add_assignee(cu, rfi),
        "can_forward": can_forward(cu, rfi),
        "can_delete": can_delete_rfi(cu, rfi),
        "can_restore": can_restore_rfi(cu, rfi),
        "is_creator": _is_creator(cu, rfi),
        "is_manager": _is_manager(cu, rfi),
        "is_assignee": _is_assignee(cu, rfi),
        "is_ball_in_court": _is_ball_in_court(cu, rfi),
        "is_distribution_member": _is_distribution_member(cu, rfi),
    }


def users_for_picker(emails: Iterable[str] | None = None) -> list[User]:
    """Return the user list used by Assignees / RFI Manager / Distribution
    pickers. The W3CRM UI requests this via ``GET /api/v1/rfi-users``.
    """
    q = select(User).where(User.is_active.is_(True)).order_by(User.last_name.asc().nullslast(), User.first_name.asc().nullslast(), User.email.asc())
    if emails:
        em = [str(e).strip().lower() for e in emails if str(e or "").strip()]
        if em:
            q = select(User).where(User.email.in_(em))
    return list(db.session.scalars(q).all())
