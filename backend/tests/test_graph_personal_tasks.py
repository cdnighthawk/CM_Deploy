"""Personal Microsoft To Do + flagged Outlook mail (Graph app-only, no extra OAuth)."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.api import _notifications as mail


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
                    {
                        "id": "msg-flag",
                        "subject": "Need a decision",
                        "from": {"emailAddress": {"name": "Pat", "address": "pat@example.com"}},
                        "toRecipients": [],
                        "receivedDateTime": "2026-09-15T10:00:00Z",
                        "isRead": False,
                        "bodyPreview": "Please review",
                        "hasAttachments": False,
                        "flag": {"flagStatus": "flagged"},
                        "importance": "normal",
                        "webLink": "https://outlook.office.com/mail/id/msg-flag",
                    }
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
                {
                    "id": "msg-flag",
                    "subject": "Flagged in Outlook",
                    "from": {"emailAddress": {"address": "pat@example.com"}},
                    "toRecipients": [],
                    "receivedDateTime": "2026-09-15T10:00:00Z",
                    "isRead": True,
                    "bodyPreview": "",
                    "hasAttachments": False,
                    "flag": {"flagStatus": "flagged"},
                }
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
