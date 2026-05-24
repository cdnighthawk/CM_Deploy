"""Object storage: local disk and mocked B2 (S3-compatible)."""

from __future__ import annotations

import io
import uuid
from unittest.mock import MagicMock, patch

import pytest
from werkzeug.datastructures import FileStorage


def test_local_save_and_send(flask_app, tmp_path):
    flask_app.config.update(
        {
            "HR_I9_DOCUMENT_UPLOAD_FOLDER": str(tmp_path),
            "B2_APPLICATION_KEY_ID": None,
            "B2_APPLICATION_KEY": None,
            "B2_BUCKET_NAME": None,
            "B2_ENDPOINT": None,
        }
    )
    with flask_app.app_context():
        from app.services.object_storage import (
            UploadCategory,
            delete_stored,
            local_path,
            save_upload,
            send_stored_file,
            stored_exists,
        )

        name = f"{uuid.uuid4()}.png"
        fs = FileStorage(
            stream=io.BytesIO(b"\x89PNG"),
            filename="photo.png",
            content_type="image/png",
        )
        sz = save_upload(UploadCategory.HR_I9, name, fs)
        assert sz == 4
        assert stored_exists(UploadCategory.HR_I9, name)
        assert local_path(UploadCategory.HR_I9, name).is_file()

        delete_stored(UploadCategory.HR_I9, name)
        assert not stored_exists(UploadCategory.HR_I9, name)

        # Re-save for download test (Windows may lock the file until the response is consumed).
        save_upload(UploadCategory.HR_I9, name, FileStorage(
            stream=io.BytesIO(b"\x89PNG"),
            filename="photo.png",
            content_type="image/png",
        ))
        with flask_app.test_request_context():
            resp = send_stored_file(
                UploadCategory.HR_I9,
                name,
                mimetype="image/png",
                download_name="photo.png",
            )
            assert resp is not None


def test_local_save_bytesio_payload(flask_app, tmp_path):
    """Drawing upload passes ``BytesIO`` — must not call ``FileStorage.save``."""
    flask_app.config.update(
        {
            "DRAWING_UPLOAD_FOLDER": str(tmp_path),
            "B2_APPLICATION_KEY_ID": None,
            "B2_APPLICATION_KEY": None,
            "B2_BUCKET_NAME": None,
            "B2_ENDPOINT": None,
        }
    )
    with flask_app.app_context():
        from app.services.object_storage import UploadCategory, local_path, save_upload

        name = f"{uuid.uuid4()}.pdf"
        payload = b"%PDF-1.4 test"
        sz = save_upload(UploadCategory.DRAWINGS, name, io.BytesIO(payload))
        assert sz == len(payload)
        assert local_path(UploadCategory.DRAWINGS, name).read_bytes() == payload


def test_b2_enabled_when_all_vars_set(flask_app):
    flask_app.config.update(
        {
            "B2_APPLICATION_KEY_ID": "key-id",
            "B2_APPLICATION_KEY": "secret",
            "B2_BUCKET_NAME": "usis-cm",
            "B2_ENDPOINT": "https://s3.us-west-004.backblazeb2.com",
        }
    )
    with flask_app.app_context():
        from app.services.object_storage import UploadCategory, b2_enabled, object_key

        assert b2_enabled()
        assert object_key(UploadCategory.DRAWINGS, "abc.pdf") == "drawings/abc.pdf"


def test_b2_prefix_in_object_key(flask_app):
    flask_app.config.update(
        {
            "B2_APPLICATION_KEY_ID": "k",
            "B2_APPLICATION_KEY": "s",
            "B2_BUCKET_NAME": "b",
            "B2_ENDPOINT": "https://s3.us-west-004.backblazeb2.com",
            "B2_PREFIX": "prod/usis-cm",
        }
    )
    with flask_app.app_context():
        from app.services.object_storage import UploadCategory, object_key

        assert object_key(UploadCategory.HR_W4, "x.jpg") == "prod/usis-cm/hr_w4/x.jpg"


@patch("app.services.object_storage._s3_client")
def test_b2_send_stored_file_sets_content_length(mock_client_factory, flask_app):
    mock_s3 = MagicMock()
    payload = b"\x89PNG\x0d\x0a"
    mock_s3.get_object.return_value = {"Body": io.BytesIO(payload)}
    mock_client_factory.return_value = mock_s3
    flask_app.config.update(
        {
            "B2_APPLICATION_KEY_ID": "k",
            "B2_APPLICATION_KEY": "s",
            "B2_BUCKET_NAME": "usis-bucket",
            "B2_ENDPOINT": "https://s3.us-west-004.backblazeb2.com",
        }
    )
    with flask_app.app_context():
        from app.services.object_storage import UploadCategory, send_stored_file

        with flask_app.test_request_context():
            resp = send_stored_file(
                UploadCategory.HR_I9,
                "photo.png",
                mimetype="image/png",
                download_name="photo.png",
            )
        assert resp is not None
        assert resp.get_data() == payload
        assert resp.headers.get("Content-Length") == str(len(payload))


@patch("app.services.object_storage._s3_client")
def test_b2_save_upload_calls_put_object(mock_client_factory, flask_app):
    mock_s3 = MagicMock()
    mock_client_factory.return_value = mock_s3
    flask_app.config.update(
        {
            "B2_APPLICATION_KEY_ID": "k",
            "B2_APPLICATION_KEY": "s",
            "B2_BUCKET_NAME": "usis-bucket",
            "B2_ENDPOINT": "https://s3.us-west-004.backblazeb2.com",
        }
    )
    with flask_app.app_context():
        from app.services.object_storage import UploadCategory, save_upload

        fs = FileStorage(
            stream=io.BytesIO(b"pdf-bytes"),
            filename="d.pdf",
            content_type="application/pdf",
        )
        sz = save_upload(UploadCategory.DRAWINGS, "id.pdf", fs)
        assert sz == 9
        mock_s3.put_object.assert_called_once()
        call = mock_s3.put_object.call_args.kwargs
        assert call["Bucket"] == "usis-bucket"
        assert call["Key"] == "drawings/id.pdf"
        assert call["Body"] == b"pdf-bytes"
