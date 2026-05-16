"""Unit tests for I-9 document filesystem helpers (no database)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest


def test_i9_document_disk_path_under_instance(flask_app, tmp_path):
    flask_app.config["HR_I9_DOCUMENT_UPLOAD_FOLDER"] = str(tmp_path)
    with flask_app.app_context():
        from app.services.hr_i9_documents import disk_path, i9_document_upload_dir

        root = i9_document_upload_dir()
        assert root == tmp_path.resolve()
        fid = uuid.uuid4()
        p = disk_path(fid, ".png")
        assert p == tmp_path / f"{fid}.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"\x89PNG")
        assert p.is_file()
