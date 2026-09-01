"""Latest USISPdfApp installer lookup and admin download routes."""
from __future__ import annotations

import uuid
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import Role, User, UserRole
from app.services import desktop_app as desktop_app_svc


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


@pytest.fixture(autouse=True)
def _clear_desktop_cache():
    desktop_app_svc.clear_cache()
    yield
    desktop_app_svc.clear_cache()


def _release_payload(filename="USIS-0.1.84-Setup.exe", asset_id=9001):
    return {
        "tag_name": "0.1.84",
        "html_url": "https://github.com/US-Interior-Specialties/USIS_PDF_App/releases/tag/0.1.84",
        "assets": [
            {"id": 1, "name": "RELEASES", "size": 80},
            {"id": 2, "name": "USIS-0.1.84-full.nupkg", "size": 40_000_000},
            {"id": asset_id, "name": filename, "size": 52_000_000},
        ],
    }


def test_pick_setup_asset_prefers_named_installer():
    asset = desktop_app_svc.pick_setup_asset(_release_payload()["assets"])
    assert asset is not None
    assert asset["name"] == "USIS-0.1.84-Setup.exe"
    assert desktop_app_svc.version_from_setup_name(asset["name"], "v9") == "0.1.84"


def test_latest_setup_from_github(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/releases/latest")
        assert request.headers.get("Authorization") == "Bearer tok"
        return httpx.Response(200, json=_release_payload())

    item = desktop_app_svc.latest_setup(
        {
            "GITHUB_DESKTOP_TOKEN": "tok",
            "GITHUB_DESKTOP_OWNER": "US-Interior-Specialties",
            "GITHUB_DESKTOP_REPO": "USIS_PDF_App",
        },
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        use_cache=False,
    )
    assert item.version == "0.1.84"
    assert item.filename == "USIS-0.1.84-Setup.exe"
    assert item.asset_id == 9001
    assert item.source == "github"


def test_latest_setup_local_fallback(tmp_path: Path):
    setup = tmp_path / "USIS-0.1.90-Setup.exe"
    setup.write_bytes(b"MZ-local")
    item = desktop_app_svc.latest_setup(
        {
            "GITHUB_DESKTOP_TOKEN": "",
            "GITHUB_FEEDBACK_TOKEN": "",
            "GITHUB_DESKTOP_LOCAL_SETUP": str(tmp_path),
        },
        use_cache=False,
    )
    assert item.source == "local"
    assert item.version == "0.1.90"
    assert item.local_path == str(setup)


def test_latest_setup_unconfigured():
    with pytest.raises(desktop_app_svc.DesktopAppError) as exc:
        desktop_app_svc.latest_setup(
            {"GITHUB_DESKTOP_TOKEN": "", "GITHUB_FEEDBACK_TOKEN": "", "GITHUB_DESKTOP_LOCAL_SETUP": ""},
            use_cache=False,
        )
    assert exc.value.status == 503


def test_admin_desktop_app_requires_admin(client, no_dev_admin):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        u = User(email="std_" + uuid.uuid4().hex[:8] + "@t.com", first_name="S", last_name="T")
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        uid = str(u.id)
        db.session.commit()

    r = client.get("/api/v1/admin/desktop-app", headers={"X-Usis-User-Id": uid})
    assert r.status_code == 403


def test_admin_desktop_app_download_local(client, flask_app, tmp_path: Path):
    setup = tmp_path / "USIS-0.1.91-Setup.exe"
    setup.write_bytes(b"MZ-installer")
    flask_app.config.update(
        GITHUB_DESKTOP_TOKEN="",
        GITHUB_FEEDBACK_TOKEN="",
        GITHUB_DESKTOP_LOCAL_SETUP=str(setup),
    )
    r = client.get("/api/v1/admin/desktop-app")
    assert r.status_code == 200
    item = r.get_json()["item"]
    assert item["version"] == "0.1.91"
    assert item["filename"] == "USIS-0.1.91-Setup.exe"
    assert item["download_path"] == "/api/v1/admin/desktop-app/download"

    dl = client.get("/api/v1/admin/desktop-app/download")
    assert dl.status_code == 200
    assert dl.data == b"MZ-installer"
    assert "USIS-0.1.91-Setup.exe" in (dl.headers.get("Content-Disposition") or "")


def test_admin_desktop_app_download_github(client, flask_app, monkeypatch):
    payload = _release_payload()
    installer = b"MZ-github-bytes"

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/releases/latest"):
            return httpx.Response(200, json=payload)
        if path.endswith("/releases/assets/9001"):
            assert request.headers.get("Accept") == "application/octet-stream"
            return httpx.Response(200, content=installer)
        return httpx.Response(404, json={"message": "not found"})

    mock = httpx.Client(transport=httpx.MockTransport(handler))
    orig_latest = desktop_app_svc.latest_setup
    orig_iter = desktop_app_svc.iter_github_asset

    def latest(config, client=None, *, use_cache=True):
        return orig_latest(config, client=mock, use_cache=False)

    def iterate(config, item, client=None):
        return orig_iter(config, item, client=mock)

    monkeypatch.setattr(desktop_app_svc, "latest_setup", latest)
    monkeypatch.setattr(desktop_app_svc, "iter_github_asset", iterate)
    flask_app.config.update(
        GITHUB_DESKTOP_TOKEN="tok",
        GITHUB_DESKTOP_OWNER="US-Interior-Specialties",
        GITHUB_DESKTOP_REPO="USIS_PDF_App",
        GITHUB_DESKTOP_LOCAL_SETUP="",
    )

    r = client.get("/api/v1/admin/desktop-app")
    assert r.status_code == 200
    assert r.get_json()["item"]["version"] == "0.1.84"

    dl = client.get("/api/v1/admin/desktop-app/download")
    assert dl.status_code == 200
    assert dl.data == installer


def test_desktop_app_module_route():
    from app.api._module_routes import resolve_modules

    assert resolve_modules("/api/v1/admin/desktop-app") == ("user_admin",)
    assert resolve_modules("/api/v1/admin/desktop-app/download") == ("user_admin",)
