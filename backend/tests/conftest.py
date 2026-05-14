"""Pytest fixtures for Flask app + HTTP client."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("TAKEOFF_API_WRITES_ENABLED", "true")
os.environ.setdefault("FLASK_ENV", "development")
# Most tests call the API without a browser session; opt in to legacy dev-open mode.
os.environ.setdefault("USIS_API_DEV_ALLOW_ANY", "1")


@pytest.fixture
def flask_app():
    """Named ``flask_app`` (not ``app``) so a globally installed ``pytest-flask`` plugin
    does not try to wrap our factory and break collection."""
    from app import create_app

    return create_app()


@pytest.fixture
def client(flask_app):
    return flask_app.test_client()
