"""Union document upload path helpers."""

from __future__ import annotations

import uuid


def test_union_document_disk_path_under_instance(flask_app, tmp_path):
    with flask_app.app_context():
        from app.services.hr_union_documents import disk_path, union_document_upload_dir

        flask_app.config["HR_UNION_DOCUMENT_UPLOAD_FOLDER"] = str(tmp_path)
        root = union_document_upload_dir()
        assert root == tmp_path.resolve()
        fid = uuid.uuid4()
        p = disk_path(fid, ".png")
        assert p.parent == root
        assert p.name == f"{fid}.png"
