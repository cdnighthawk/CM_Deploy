"""USIS-REF footer format, append, and parse."""
from __future__ import annotations

import uuid

from app.api._email_ref import append_ref, correspondence_archive_mailbox, format_ref_block, parse_ref


def test_format_and_parse_roundtrip():
    pid = uuid.uuid4()
    tid = uuid.uuid4()
    block = format_ref_block(pid, tid)
    assert "USIS-REF" in block
    assert parse_ref(block) == (pid, tid)


def test_append_skips_when_footer_already_present():
    pid = uuid.uuid4()
    tid = uuid.uuid4()
    body, html, out_tid = append_ref("Hello", "<p>Hello</p>", pid, tid)
    again, again_html, again_tid = append_ref(body, html, pid, uuid.uuid4())
    assert again == body
    assert again_html == html
    assert again_tid == tid
    assert body.count("USIS-REF") == 1


def test_parse_uses_last_match_in_quoted_reply():
    old_p, old_t = uuid.uuid4(), uuid.uuid4()
    new_p, new_t = uuid.uuid4(), uuid.uuid4()
    text = (
        "New reply at the top\n\n"
        f"USIS-REF project={new_p} thread={new_t}\n"
        "> quoted original\n"
        "-----\n"
        f"USIS-REF project={old_p} thread={old_t}\n"
    )
    assert parse_ref(text) == (old_p, old_t)


def test_parse_finds_ref_after_html_strip_style_body():
    pid = uuid.uuid4()
    tid = uuid.uuid4()
    html = (
        "<div>Please review</div>"
        f'<p style="margin-top:1.5em;color:#666;font-size:12px;">-----<br>\n'
        f"USIS-REF project={pid} thread={tid}</p>"
    )
    assert parse_ref(html) == (pid, tid)


def test_parse_ignores_invalid_uuid():
    assert parse_ref("USIS-REF project=not-a-uuid thread=also-bad") is None
    assert parse_ref("no marker here") is None
    assert parse_ref("") is None


def test_append_without_project_leaves_body():
    body, html, tid = append_ref("Hello", "<p>Hi</p>", None)
    assert body == "Hello"
    assert html == "<p>Hi</p>"
    assert tid is None


def test_correspondence_archive_mailbox_first_address(flask_app, monkeypatch):
    monkeypatch.setenv("CORRESPONDENCE_MAILBOXES", "projects@gousis.com, other@gousis.com")
    with flask_app.app_context():
        flask_app.config["CORRESPONDENCE_MAILBOXES"] = "projects@gousis.com, other@gousis.com"
        assert correspondence_archive_mailbox() == "projects@gousis.com"
