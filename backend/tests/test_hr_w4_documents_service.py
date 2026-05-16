"""Unit tests for W-4 document filesystem helpers (no database)."""

from __future__ import annotations

import uuid
from pathlib import Path


def test_w4_document_disk_path_under_instance(flask_app, tmp_path):
    flask_app.config["HR_W4_DOCUMENT_UPLOAD_FOLDER"] = str(tmp_path)
    with flask_app.app_context():
        from app.services.hr_w4_documents import disk_path, w4_document_upload_dir

        root = w4_document_upload_dir()
        assert root == tmp_path.resolve()
        fid = uuid.uuid4()
        p = disk_path(fid, ".png")
        assert p == tmp_path / f"{fid}.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"\x89PNG")
        assert p.is_file()
