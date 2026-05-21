"""Config defaults when a custom public URL is set on Render."""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def reload_config(monkeypatch):
    """Reload ``app.config`` after env changes (module reads env at import)."""
    monkeypatch.delenv("USIS_POST_LOGIN_REDIRECT", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    monkeypatch.delenv("USIS_APP_PUBLIC_URL", raising=False)
    import app.config as config_mod

    importlib.reload(config_mod)
    yield config_mod
    importlib.reload(config_mod)


def test_public_url_drives_cors_and_post_login(reload_config, monkeypatch):
    monkeypatch.setenv("USIS_APP_PUBLIC_URL", "https://www.usiscm.com/")
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://usis-cm.onrender.com")
    importlib.reload(reload_config)

    assert reload_config.Config.CORS_ORIGINS == (
        "https://www.usiscm.com",
        "https://usiscm.com",
        "https://usis-cm.onrender.com",
        "https://www.usis-cm.onrender.com",
    )
    assert reload_config.Config.USIS_POST_LOGIN_REDIRECT == "https://www.usiscm.com/usis-dashboard-dark.html"


def test_render_external_url_when_no_public_url(reload_config, monkeypatch):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://usis-cm.onrender.com")
    importlib.reload(reload_config)

    assert reload_config.Config.CORS_ORIGINS == (
        "https://usis-cm.onrender.com",
        "https://www.usis-cm.onrender.com",
    )
    assert reload_config.Config.USIS_POST_LOGIN_REDIRECT == "https://usis-cm.onrender.com/usis-dashboard-dark.html"
