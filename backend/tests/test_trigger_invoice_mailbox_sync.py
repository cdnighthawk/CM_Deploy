"""Render cron helper for POST /api/v1/ap/mailbox/sync."""
from __future__ import annotations

import importlib.util
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "trigger_invoice_mailbox_sync.py"


def _load():
    spec = importlib.util.spec_from_file_location("trigger_invoice_mailbox_sync", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def cron():
    return _load()


def test_resolve_urls_prefers_private_hostport(cron, monkeypatch):
    monkeypatch.setenv("USIS_WEB_HOSTPORT", "usis-cm:10000")
    monkeypatch.setenv("INVOICE_MAILBOX_SYNC_URL", "https://www.usiscm.com/api/v1/ap/mailbox/sync")
    assert cron.resolve_urls()[0] == "http://usis-cm:10000/api/v1/ap/mailbox/sync"
    assert cron.resolve_urls()[1] == "https://www.usiscm.com/api/v1/ap/mailbox/sync"


def test_resolve_urls_defaults_to_public_site(cron, monkeypatch):
    monkeypatch.delenv("USIS_WEB_HOSTPORT", raising=False)
    monkeypatch.delenv("INVOICE_MAILBOX_SYNC_URL", raising=False)
    assert cron.resolve_urls() == [cron.DEFAULT_URL]


def test_main_requires_secret(cron, monkeypatch, capsys):
    monkeypatch.delenv("BC_SYNC_CRON_SECRET", raising=False)
    assert cron.main() == 1
    assert "BC_SYNC_CRON_SECRET is required" in capsys.readouterr().err


def test_main_succeeds_on_first_url(cron, monkeypatch, capsys):
    monkeypatch.setenv("BC_SYNC_CRON_SECRET", "shared-secret")
    monkeypatch.setenv("USIS_WEB_HOSTPORT", "usis-cm:10000")
    monkeypatch.setattr(cron, "post_sync", lambda url, secret, timeout=170: (200, '{"created":0}'))
    assert cron.main() == 0
    out = capsys.readouterr().out
    assert "200" in out
    assert "created" in out


def test_main_falls_back_when_private_network_fails(cron, monkeypatch):
    monkeypatch.setenv("BC_SYNC_CRON_SECRET", "shared-secret")
    monkeypatch.setenv("USIS_WEB_HOSTPORT", "usis-cm:10000")
    monkeypatch.setenv("INVOICE_MAILBOX_SYNC_URL", "https://www.usiscm.com/api/v1/ap/mailbox/sync")
    seen: list[str] = []

    def fake_post(url, secret, timeout=170):
        seen.append(url)
        if url.startswith("http://"):
            raise URLError("connection refused")
        return 200, '{"created":1}'

    monkeypatch.setattr(cron, "post_sync", fake_post)
    assert cron.main() == 0
    assert seen[0].startswith("http://usis-cm:10000")
    assert seen[1].startswith("https://www.usiscm.com")


def test_main_401_does_not_retry(cron, monkeypatch, capsys):
    monkeypatch.setenv("BC_SYNC_CRON_SECRET", "wrong-secret")
    monkeypatch.setenv("USIS_WEB_HOSTPORT", "usis-cm:10000")
    monkeypatch.setenv("INVOICE_MAILBOX_SYNC_URL", "https://www.usiscm.com/api/v1/ap/mailbox/sync")
    seen: list[str] = []

    def fake_post(url, secret, timeout=170):
        seen.append(url)
        raise HTTPError(url, 401, "Unauthorized", hdrs=None, fp=BytesIO(b'{"error":"authentication required"}'))

    monkeypatch.setattr(cron, "post_sync", fake_post)
    assert cron.main() == 1
    assert seen == ["http://usis-cm:10000/api/v1/ap/mailbox/sync"]
    err = capsys.readouterr().err
    assert "401" in err
    assert "matches the usis-cm web service" in err
