"""Personal Microsoft To Do tasks and Outlook flagged mail for the signed-in user.

Uses the same Entra app-only Graph token as mailbox sync (client credentials),
scoped to the session user's mailbox. Does not add a second OAuth flow.
"""
from __future__ import annotations

from typing import Any

from . import _notifications as graph
from ._notifications import GraphMailError, _FLAG_STATUSES, _MAIL_LIST_SELECT, patch_mailbox_message

_TODO_TASK_SELECT = (
    "id,title,status,importance,dueDateTime,createdDateTime,"
    "lastModifiedDateTime,isReminderOn,completedDateTime"
)
_SKIP_TODO_LISTS = frozenset({"flaggedemails"})
_OPEN_TODO_STATUSES = frozenset({"notstarted", "inprogress", "waitingonothers", "deferred", ""})


def _source_error(exc: GraphMailError, *, permission: str) -> dict[str, Any]:
    status = int(exc.status_code or 502)
    if status in (401, 403):
        return {
            "ok": False,
            "error": (
                "Microsoft Graph refused this source. Confirm application "
                f"{permission} is granted with admin consent on the USIS CRM "
                "Entra app."
            ),
            "detail": str(exc),
        }
    if status == 404:
        return {
            "ok": False,
            "error": "Microsoft 365 did not find this mailbox or To Do list.",
            "detail": str(exc),
        }
    return {"ok": False, "error": str(exc), "detail": str(exc)}


def _due_from_todo(item: dict[str, Any]) -> str | None:
    due = item.get("dueDateTime") if isinstance(item.get("dueDateTime"), dict) else {}
    raw = str(due.get("dateTime") or "").strip()
    return raw or None


def _serialize_todo(item: dict[str, Any], *, list_id: str, list_name: str) -> dict[str, Any]:
    status = str(item.get("status") or "notStarted")
    return {
        "kind": "todo",
        "id": item.get("id"),
        "list_id": list_id,
        "list_name": list_name,
        "title": item.get("title") or "(no title)",
        "status": status,
        "importance": str(item.get("importance") or "normal"),
        "due": _due_from_todo(item),
        "created": item.get("createdDateTime"),
        "web_link": "https://to-do.office.com/tasks",
        "from": None,
        "is_read": None,
    }


def _serialize_flagged_mail(item: dict[str, Any]) -> dict[str, Any]:
    summary = graph._serialize_message_summary(item)
    from_addr = summary.get("from") if isinstance(summary.get("from"), dict) else {}
    who = (from_addr.get("name") or from_addr.get("address") or "").strip()
    return {
        "kind": "flagged_mail",
        "id": summary.get("id"),
        "list_id": None,
        "list_name": "Flagged email",
        "title": summary.get("subject") or "(no subject)",
        "status": summary.get("flag_status") or "flagged",
        "importance": summary.get("importance") or "normal",
        "due": None,
        "created": summary.get("received"),
        "web_link": summary.get("web_link"),
        "from": who or None,
        "is_read": summary.get("is_read"),
        "preview": summary.get("preview"),
    }


def _list_todo_tasks(*, mailbox: str, top: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    url = graph._user_mail_url(mailbox, "todo", "lists")
    try:
        lists = [
            row
            for row in graph._graph_paged(url, {"$top": "50", "$select": "id,displayName,wellknownListName"})
            if isinstance(row, dict)
        ]
    except GraphMailError as exc:
        return [], _source_error(exc, permission="Tasks.Read.All")

    items: list[dict[str, Any]] = []
    per_list = max(5, min(top, 25))
    for lst in lists:
        well = str(lst.get("wellknownListName") or "").strip().lower()
        if well in _SKIP_TODO_LISTS:
            continue
        list_id = str(lst.get("id") or "").strip()
        if not list_id:
            continue
        list_name = str(lst.get("displayName") or "Tasks").strip() or "Tasks"
        tasks_url = graph._user_mail_url(mailbox, "todo", "lists", list_id, "tasks")
        params = {
            "$top": str(per_list),
            "$select": _TODO_TASK_SELECT,
            "$filter": "status ne 'completed'",
        }
        try:
            payload = graph._graph_http("GET", tasks_url, params=params) or {}
        except GraphMailError:
            try:
                payload = graph._graph_http(
                    "GET",
                    tasks_url,
                    params={"$top": str(per_list), "$select": _TODO_TASK_SELECT},
                ) or {}
            except GraphMailError:
                continue
        for raw in payload.get("value") or []:
            if not isinstance(raw, dict):
                continue
            status = str(raw.get("status") or "").strip().lower()
            if status == "completed":
                continue
            if status and status not in _OPEN_TODO_STATUSES:
                continue
            items.append(_serialize_todo(raw, list_id=list_id, list_name=list_name))
            if len(items) >= top:
                return items, {"ok": True, "error": None}
    return items, {"ok": True, "error": None}


def _list_flagged_mail(*, mailbox: str, top: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    url = graph._user_mail_url(mailbox, "messages")
    params = {
        "$top": str(max(1, min(top, 50))),
        "$select": _MAIL_LIST_SELECT,
        "$filter": "flag/flagStatus eq 'flagged'",
        "$orderby": "receivedDateTime desc",
    }
    try:
        payload = graph._graph_http("GET", url, params=params) or {}
    except GraphMailError as exc:
        if int(exc.status_code or 0) == 400:
            try:
                lighter = dict(params)
                lighter.pop("$orderby", None)
                payload = graph._graph_http("GET", url, params=lighter) or {}
            except GraphMailError as retry_exc:
                return [], _source_error(retry_exc, permission="Mail.ReadWrite")
        else:
            return [], _source_error(exc, permission="Mail.ReadWrite")
    items = [
        _serialize_flagged_mail(row)
        for row in (payload.get("value") or [])
        if isinstance(row, dict)
    ]
    return items, {"ok": True, "error": None}


def _sort_key(item: dict[str, Any]) -> tuple[int, str]:
    due = str(item.get("due") or item.get("created") or "")
    high = 0 if str(item.get("importance") or "").lower() == "high" else 1
    return (high, due or "9999")


def list_personal_tasks(*, mailbox: str, top: int = 40) -> dict[str, Any]:
    """To Do tasks plus flagged Outlook mail for ``mailbox`` (signed-in user)."""
    if not graph._graph_credentials_present():
        raise GraphMailError(503, "Microsoft Graph is not configured.")
    n = max(1, min(int(top or 40), 50))
    todo_items, todo_src = _list_todo_tasks(mailbox=mailbox, top=n)
    mail_items, mail_src = _list_flagged_mail(mailbox=mailbox, top=n)
    items = todo_items + mail_items
    items.sort(key=_sort_key)
    return {
        "mailbox": mailbox,
        "items": items[:n],
        "sources": {"todo": todo_src, "flagged_mail": mail_src},
    }


def complete_personal_task(
    *,
    mailbox: str,
    kind: str,
    item_id: str,
    list_id: str | None = None,
) -> dict[str, Any]:
    """Complete a To Do task or clear an Outlook flag for ``mailbox``."""
    if not graph._graph_credentials_present():
        raise GraphMailError(503, "Microsoft Graph is not configured.")
    k = str(kind or "").strip().lower()
    oid = str(item_id or "").strip()
    if not oid:
        raise GraphMailError(400, "id is required")
    if k == "todo":
        lid = str(list_id or "").strip()
        if not lid:
            raise GraphMailError(400, "list_id is required for To Do tasks")
        url = graph._user_mail_url(mailbox, "todo", "lists", lid, "tasks", oid)
        try:
            graph._graph_http("PATCH", url, json={"status": "completed"})
        except GraphMailError as exc:
            if int(exc.status_code or 0) in (401, 403):
                raise GraphMailError(
                    403,
                    "Microsoft Graph refused to update To Do. Confirm application "
                    "Tasks.ReadWrite.All is granted with admin consent.",
                ) from exc
            raise
        return {"ok": True, "kind": "todo", "id": oid, "status": "completed"}
    if k in ("flagged_mail", "mail", "flagged"):
        return patch_mailbox_message(
            mailbox=mailbox,
            message_id=oid,
            flag_status="notFlagged",
        ) | {"kind": "flagged_mail", "id": oid}
    raise GraphMailError(400, "kind must be todo or flagged_mail")


def parse_flag_status(value: Any) -> str | None:
    if value is None:
        return None
    status = str(value).strip()
    if not status:
        return None
    if status not in _FLAG_STATUSES:
        raise GraphMailError(400, "flag_status must be flagged, notFlagged, or complete")
    return status
