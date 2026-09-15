"""Personal Microsoft To Do + flagged Outlook mail (Graph app-only, no extra OAuth)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.api import _notifications as mail
from app.api import _graph_personal as gp


def _utc(year, month, day, hour=0, minute=0, second=0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _flagged_message(*, msg_id: str, subject: str, received: str) -> dict:
    return {
        "id": msg_id,
        "subject": subject,
        "from": {"emailAddress": {"name": "Pat", "address": "pat@example.com"}},
        "toRecipients": [],
        "receivedDateTime": received,
        "isRead": False,
        "bodyPreview": "Please review",
        "hasAttachments": False,
        "flag": {"flagStatus": "flagged"},
        "importance": "normal",
        "webLink": f"https://outlook.office.com/mail/id/{msg_id}",
    }


def _session_user(email: str):
    cu = MagicMock()
    cu.user = MagicMock()
    cu.user.email = email
    return cu


def _graph_env(monkeypatch):
    monkeypatch.setenv("MS_ENTRA_TENANT_ID", "tenant-id")
    monkeypatch.setenv("MS_ENTRA_CLIENT_ID", "client-id")
    monkeypatch.setenv("MS_ENTRA_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("MAIL_FROM", "noreply@gousis.com")
    mail.reset_graph_token_cache()


def test_me_tasks_uses_session_mailbox_not_query(client, monkeypatch):
    from app.api import v1 as v1_mod

    staff = "charles@gousis.com"
    monkeypatch.setattr(v1_mod, "current_user", lambda: _session_user(staff))
    _graph_env(monkeypatch)
    captured: list[str] = []

    def fake_http(method, url, **kwargs):
        captured.append(url)
        if "/todo/lists" in url and "/tasks" not in url:
            return {
                "value": [
                    {
                        "id": "list-1",
                        "displayName": "Tasks",
                        "wellknownListName": "defaultList",
                    },
                    {
                        "id": "list-flagged",
                        "displayName": "Flagged Email",
                        "wellknownListName": "flaggedEmails",
                    },
                ]
            }
        if "/todo/lists/list-1/tasks" in url:
            return {
                "value": [
                    {
                        "id": "task-1",
                        "title": "Call the GC",
                        "status": "notStarted",
                        "importance": "high",
                        "dueDateTime": {"dateTime": "2026-09-16T00:00:00", "timeZone": "UTC"},
                        "createdDateTime": "2026-09-14T12:00:00Z",
                    }
                ]
            }
        if url.rstrip("/").endswith("/messages") or "/messages?" in url:
            return {
                "value": [
                    _flagged_message(
                        msg_id="msg-flag",
                        subject="Need a decision",
                        received=_iso(datetime.now(timezone.utc) - timedelta(days=1)),
                    )
                ]
            }
        raise AssertionError(f"unexpected Graph URL {url}")

    monkeypatch.setattr(mail, "_graph_http", fake_http)
    r = client.get("/api/v1/me/tasks", query_string={"mailbox": "victim@gousis.com"})
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["mailbox"] == staff
    kinds = {item["kind"] for item in body["items"]}
    assert kinds == {"todo", "flagged_mail"}
    titles = {item["title"] for item in body["items"]}
    assert "Call the GC" in titles
    assert "Need a decision" in titles
    flagged = next(item for item in body["items"] if item["kind"] == "flagged_mail")
    todo = next(item for item in body["items"] if item["kind"] == "todo")
    assert flagged["id"] == "msg-flag"
    assert todo["id"] == "task-1"
    assert todo["web_link"] == "https://to-do.office.com/tasks"
    assert all("victim@" not in url for url in captured)
    assert any("todo/lists" in url for url in captured)
    assert not any("list-flagged" in url for url in captured)
    assert body["sources"]["todo"]["ok"] is True
    assert body["sources"]["flagged_mail"]["ok"] is True


def test_me_tasks_keeps_flagged_mail_when_todo_forbidden(client, monkeypatch):
    from app.api import v1 as v1_mod

    staff = "charles@gousis.com"
    monkeypatch.setattr(v1_mod, "current_user", lambda: _session_user(staff))
    _graph_env(monkeypatch)

    def fake_http(method, url, **kwargs):
        if "/todo/" in url:
            raise mail.GraphMailError(403, "Access denied")
        return {
            "value": [
                _flagged_message(
                    msg_id="msg-flag",
                    subject="Flagged in Outlook",
                    received=_iso(datetime.now(timezone.utc) - timedelta(days=1)),
                )
            ]
        }

    monkeypatch.setattr(mail, "_graph_http", fake_http)
    r = client.get("/api/v1/me/tasks")
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["items"][0]["kind"] == "flagged_mail"
    assert body["sources"]["todo"]["ok"] is False
    assert "Tasks.Read.All" in (body["sources"]["todo"]["error"] or "")
    assert body["sources"]["flagged_mail"]["ok"] is True


def test_complete_todo_uses_session_user(client, monkeypatch):
    from app.api import v1 as v1_mod

    staff = "charles@gousis.com"
    monkeypatch.setattr(v1_mod, "current_user", lambda: _session_user(staff))
    _graph_env(monkeypatch)
    captured: list[tuple[str, str, dict]] = []

    def fake_http(method, url, **kwargs):
        captured.append((method, url, kwargs.get("json") or {}))
        return None

    monkeypatch.setattr(mail, "_graph_http", fake_http)
    r = client.post(
        "/api/v1/me/tasks/complete",
        json={"kind": "todo", "id": "task-1", "list_id": "list-1", "mailbox": "victim@gousis.com"},
    )
    assert r.status_code == 200, r.get_json()
    assert captured
    method, url, payload = captured[0]
    assert method == "PATCH"
    assert "charles%40gousis.com" in url or "charles@gousis.com" in url
    assert "victim@" not in url
    assert "/todo/lists/list-1/tasks/task-1" in url
    assert payload == {"status": "completed"}


def test_complete_flagged_mail_clears_flag(client, monkeypatch):
    from app.api import v1 as v1_mod

    staff = "charles@gousis.com"
    monkeypatch.setattr(v1_mod, "current_user", lambda: _session_user(staff))
    _graph_env(monkeypatch)
    captured: list[tuple[str, dict]] = []

    def fake_http(method, url, **kwargs):
        captured.append((url, kwargs.get("json") or {}))
        return None

    monkeypatch.setattr(mail, "_graph_http", fake_http)
    r = client.post(
        "/api/v1/me/tasks/complete",
        json={"kind": "flagged_mail", "id": "AAMkAGI"},
    )
    assert r.status_code == 200, r.get_json()
    url, payload = captured[0]
    assert "messages/AAMkAGI" in url
    assert payload == {"flag": {"flagStatus": "notFlagged"}}


def test_patch_mail_flag_does_not_force_read(client, monkeypatch):
    from app.api import v1 as v1_mod

    staff = "charles@gousis.com"
    monkeypatch.setattr(v1_mod, "current_user", lambda: _session_user(staff))
    captured: list[dict] = []

    def fake_http(method, url, **kwargs):
        captured.append(kwargs.get("json") or {})
        return None

    monkeypatch.setattr(mail, "_graph_http", fake_http)
    r = client.patch("/api/v1/mail/messages/AAMkAGI", json={"flag_status": "flagged"})
    assert r.status_code == 200, r.get_json()
    assert captured == [{"flag": {"flagStatus": "flagged"}}]
    assert r.get_json()["flag_status"] == "flagged"


def test_patch_mail_empty_body_still_marks_read(client, monkeypatch):
    from app.api import v1 as v1_mod

    monkeypatch.setattr(v1_mod, "current_user", lambda: _session_user("charles@gousis.com"))
    captured: list[dict] = []

    def fake_http(method, url, **kwargs):
        captured.append(kwargs.get("json") or {})
        return None

    monkeypatch.setattr(mail, "_graph_http", fake_http)
    r = client.patch("/api/v1/mail/messages/AAMkAGI", json={})
    assert r.status_code == 200
    assert captured == [{"isRead": True}]


def test_me_tasks_requires_sign_in(client, monkeypatch):
    from app.api import v1 as v1_mod

    cu = MagicMock()
    cu.user = None
    monkeypatch.setattr(v1_mod, "current_user", lambda: cu)
    r = client.get("/api/v1/me/tasks")
    assert r.status_code == 401


def test_list_flagged_mail_graph_filter_includes_30_day_received_cutoff(monkeypatch):
    captured: list[dict] = []
    now = _utc(2026, 9, 15, 16, 27, 0)
    monkeypatch.setattr(gp, "_utcnow", lambda: now)

    def fake_http(method, url, **kwargs):
        captured.append(kwargs.get("params") or {})
        return {"value": []}

    monkeypatch.setattr(mail, "_graph_http", fake_http)
    items, src = gp._list_flagged_mail(mailbox="charles@gousis.com", top=10)
    assert items == []
    assert src["ok"] is True
    assert captured
    params = captured[0]
    assert params["$orderby"] == "receivedDateTime desc"
    filt = params["$filter"]
    assert "flag/flagStatus eq 'flagged'" in filt
    assert "receivedDateTime ge 2026-08-16T16:27:00Z" in filt


def test_list_flagged_mail_drops_messages_older_than_30_days(monkeypatch):
    now = _utc(2026, 9, 15, 12, 0, 0)
    monkeypatch.setattr(gp, "_utcnow", lambda: now)

    def fake_http(method, url, **kwargs):
        return {
            "value": [
                _flagged_message(
                    msg_id="msg-recent",
                    subject="Recent flag",
                    received="2026-09-10T10:00:00Z",
                ),
                _flagged_message(
                    msg_id="msg-old",
                    subject="Ancient flag",
                    received="2024-03-01T10:00:00Z",
                ),
                _flagged_message(
                    msg_id="msg-boundary",
                    subject="Exactly 30 days",
                    received="2026-08-16T12:00:00Z",
                ),
                _flagged_message(
                    msg_id="msg-just-old",
                    subject="31st day",
                    received="2026-08-16T11:59:59Z",
                ),
            ]
        }

    monkeypatch.setattr(mail, "_graph_http", fake_http)
    items, src = gp._list_flagged_mail(mailbox="charles@gousis.com", top=40)
    assert src["ok"] is True
    assert {row["id"] for row in items} == {"msg-recent", "msg-boundary"}
    assert {row["title"] for row in items} == {"Recent flag", "Exactly 30 days"}


def test_list_flagged_mail_retries_without_orderby_then_client_filters(monkeypatch):
    now = _utc(2026, 9, 15, 12, 0, 0)
    monkeypatch.setattr(gp, "_utcnow", lambda: now)
    captured: list[dict] = []

    def fake_http(method, url, **kwargs):
        params = kwargs.get("params") or {}
        captured.append(params)
        if params.get("$orderby"):
            raise mail.GraphMailError(400, "The restriction or sort order is invalid.")
        return {
            "value": [
                _flagged_message(
                    msg_id="msg-recent",
                    subject="Keep me",
                    received="2026-09-01T08:00:00Z",
                ),
                _flagged_message(
                    msg_id="msg-old",
                    subject="Drop me",
                    received="2025-01-15T08:00:00Z",
                ),
            ]
        }

    monkeypatch.setattr(mail, "_graph_http", fake_http)
    items, src = gp._list_flagged_mail(mailbox="charles@gousis.com", top=20)
    assert src["ok"] is True
    assert len(captured) == 2
    assert captured[0].get("$orderby") == "receivedDateTime desc"
    assert "receivedDateTime ge" in captured[0]["$filter"]
    assert "$orderby" not in captured[1]
    assert "receivedDateTime ge" in captured[1]["$filter"]
    assert [row["id"] for row in items] == ["msg-recent"]


def test_list_flagged_mail_falls_back_to_client_filter_when_date_filter_rejected(monkeypatch):
    now = _utc(2026, 9, 15, 12, 0, 0)
    monkeypatch.setattr(gp, "_utcnow", lambda: now)
    captured: list[dict] = []

    def fake_http(method, url, **kwargs):
        params = kwargs.get("params") or {}
        captured.append(params)
        if "receivedDateTime" in (params.get("$filter") or ""):
            raise mail.GraphMailError(400, "Invalid filter clause.")
        return {
            "value": [
                _flagged_message(
                    msg_id="msg-old",
                    subject="Years old",
                    received="2021-06-01T00:00:00Z",
                ),
                _flagged_message(
                    msg_id="msg-recent",
                    subject="This month",
                    received="2026-09-12T00:00:00Z",
                ),
            ]
        }

    monkeypatch.setattr(mail, "_graph_http", fake_http)
    items, src = gp._list_flagged_mail(mailbox="charles@gousis.com", top=20)
    assert src["ok"] is True
    assert len(captured) == 3
    assert captured[2]["$filter"] == "flag/flagStatus eq 'flagged'"
    assert captured[2].get("$orderby") == "receivedDateTime desc"
    assert [row["id"] for row in items] == ["msg-recent"]


def test_me_tasks_excludes_old_flagged_mail_and_keeps_todo(client, monkeypatch):
    from app.api import v1 as v1_mod

    staff = "charles@gousis.com"
    monkeypatch.setattr(v1_mod, "current_user", lambda: _session_user(staff))
    _graph_env(monkeypatch)
    now = _utc(2026, 9, 15, 12, 0, 0)
    monkeypatch.setattr(gp, "_utcnow", lambda: now)
    todo_filters: list[str] = []

    def fake_http(method, url, **kwargs):
        params = kwargs.get("params") or {}
        if "/todo/lists" in url and "/tasks" not in url:
            return {
                "value": [
                    {
                        "id": "list-1",
                        "displayName": "Tasks",
                        "wellknownListName": "defaultList",
                    }
                ]
            }
        if "/todo/lists/list-1/tasks" in url:
            todo_filters.append(params.get("$filter") or "")
            return {
                "value": [
                    {
                        "id": "task-1",
                        "title": "Call the GC",
                        "status": "notStarted",
                        "importance": "high",
                        "dueDateTime": {"dateTime": "2026-09-16T00:00:00", "timeZone": "UTC"},
                        "createdDateTime": "2026-09-14T12:00:00Z",
                    }
                ]
            }
        if url.rstrip("/").endswith("/messages") or "/messages?" in url:
            return {
                "value": [
                    _flagged_message(
                        msg_id="msg-old",
                        subject="Old flagged mail",
                        received="2024-01-02T10:00:00Z",
                    ),
                    _flagged_message(
                        msg_id="msg-new",
                        subject="Need a decision",
                        received="2026-09-10T10:00:00Z",
                    ),
                ]
            }
        raise AssertionError(f"unexpected Graph URL {url}")

    monkeypatch.setattr(mail, "_graph_http", fake_http)
    r = client.get("/api/v1/me/tasks")
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    titles = {item["title"] for item in body["items"]}
    assert "Call the GC" in titles
    assert "Need a decision" in titles
    assert "Old flagged mail" not in titles
    flagged = [item for item in body["items"] if item["kind"] == "flagged_mail"]
    assert [item["id"] for item in flagged] == ["msg-new"]
    assert all(filt == "status ne 'completed'" for filt in todo_filters)
    assert body["sources"]["todo"]["ok"] is True
    assert body["sources"]["flagged_mail"]["ok"] is True
