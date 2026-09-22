"""Public WorX CM marketing homepage on worxcm.com (not usiscm.com login)."""
from __future__ import annotations

from app.static_shell import resolve_landing_root

WORX = "https://www.worxcm.com"


def test_landing_root_exists():
    root = resolve_landing_root()
    assert root is not None
    assert (root / "index.html").is_file()
    assert (root / "img" / "hero-drywall.jpg").is_file()


def test_worxcm_root_serves_landing(client):
    r = client.get("/", base_url=WORX)
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Own the" in body
    assert "WorX CM" in body
    assert 'href="img/hero-drywall.jpg"' in body or "hero-drywall.jpg" in body
    assert "/public/walkthrough" in body


def test_worxcm_index_html_is_landing_not_dashboard(client):
    r = client.get("/index.html", base_url=WORX, follow_redirects=False)
    assert r.status_code == 200
    assert b"Own the" in r.data


def test_localhost_root_is_not_the_marketing_page(client, monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers.get("Location") == "/page-login.html"


def test_worxcm_hero_image(client):
    r = client.get("/img/hero-drywall.jpg", base_url=WORX)
    assert r.status_code == 200
    assert "image" in (r.headers.get("Content-Type") or "")
    assert len(r.data) > 1000


def test_worxcm_missing_image_is_404(client):
    r = client.get("/img/no-such.jpg", base_url=WORX)
    assert r.status_code == 404


def test_walkthrough_posts_mail(client, monkeypatch):
    sent = {}

    def fake_send(**kwargs):
        sent.update(kwargs)
        return {"sent": True, "dry_run": False, "error": None}

    monkeypatch.setattr(
        "app.api._notifications.send_html_notification_email",
        fake_send,
    )
    r = client.post(
        "/public/walkthrough",
        json={
            "name": "Pat Estimator",
            "company": "Finish Co",
            "email": "pat@example.com",
            "trade": "Drywall",
            "focus": "Westview takeoff",
        },
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["sent"] is True
    assert sent["to"] == "charles@gousis.com"
    assert sent["reply_to"] == "pat@example.com"
    assert "Finish Co" in sent["subject"]
    assert "Westview takeoff" in sent["body"]


def test_walkthrough_requires_email(client):
    r = client.post(
        "/public/walkthrough",
        json={"name": "Pat", "company": "Finish Co", "email": "not-an-email"},
    )
    assert r.status_code == 400


def test_walkthrough_honeypot_is_silent(client, monkeypatch):
    def boom(**kwargs):
        raise AssertionError("honeypot must not send mail")

    monkeypatch.setattr("app.api._notifications.send_html_notification_email", boom)
    r = client.post(
        "/public/walkthrough",
        json={
            "name": "Bot",
            "company": "Spam",
            "email": "bot@example.com",
            "website": "http://spam.test",
        },
    )
    assert r.status_code == 200
    assert r.get_json()["ok"] is True
