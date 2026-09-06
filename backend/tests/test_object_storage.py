"""Object storage: local disk and mocked B2 (S3-compatible)."""

from __future__ import annotations

import io
import uuid
from pathlib import Path
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
            "B2_PREFIX": None,
        }
    )
    with flask_app.app_context():
        from app.services.object_storage import UploadCategory, b2_enabled, object_key

        assert b2_enabled()
        assert object_key(UploadCategory.DRAWINGS, "abc.pdf") == "drawings/abc.pdf"


def test_mirror_root_serves_when_local_missing(flask_app, tmp_path):
    """Without B2 credentials, local Flask may still read the NAS mirror."""
    rel = Path("24060") / "Architectural" / "Permit-Set" / "A1.pdf"
    dest = tmp_path / "prod" / "usis-cm" / "drawings" / rel
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"%PDF-1.4 nas")
    flask_app.config.update(
        {
            "DRAWING_UPLOAD_FOLDER": str(tmp_path / "empty-instance"),
            "B2_APPLICATION_KEY_ID": None,
            "B2_APPLICATION_KEY": None,
            "B2_BUCKET_NAME": None,
            "B2_ENDPOINT": None,
            "B2_PREFIX": "prod/usis-cm",
            "B2_MIRROR_ROOT": str(tmp_path),
        }
    )
    with flask_app.app_context():
        from app.services.object_storage import UploadCategory, send_stored_file, stored_exists

        name = rel.as_posix()
        assert stored_exists(UploadCategory.DRAWINGS, name)
        with flask_app.test_request_context():
            resp = send_stored_file(
                UploadCategory.DRAWINGS,
                name,
                mimetype="application/pdf",
                download_name="A1.pdf",
            )
            assert resp is not None
            assert resp.status_code == 200


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


@patch("app.services.object_storage._put_native_b2")
@patch("app.services.object_storage._s3_client")
def test_b2_put_uses_native_first(mock_client_factory, mock_native, flask_app):
    """Render writes through native B2 so the S3 gateway is not on the happy path."""
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

        sz = save_upload(UploadCategory.DOCUMENTS, "spec.pdf", io.BytesIO(b"%PDF-1.4"))
        assert sz == 8
        mock_native.assert_called_once()
        assert mock_native.call_args.args[0].endswith("documents/spec.pdf")
        mock_s3.put_object.assert_not_called()


@patch("app.services.object_storage._put_native_b2", side_effect=Exception("native fail"))
@patch("app.services.object_storage._s3_client")
def test_b2_put_falls_back_to_s3_when_native_fails(mock_client_factory, _native, flask_app):
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

        sz = save_upload(UploadCategory.DOCUMENTS, "spec.pdf", io.BytesIO(b"%PDF-1.4"))
        assert sz == 8
        mock_s3.put_object.assert_called_once()


@patch("app.services.object_storage._put_native_b2", side_effect=Exception("native fail"))
@patch("app.services.object_storage._s3_client")
def test_b2_put_exhausted_raises_storage_error(mock_client_factory, _native, flask_app):
    mock_s3 = MagicMock()
    mock_s3.put_object.side_effect = Exception(
        "SSL validation failed for https://s3.example/key EOF occurred in violation of protocol"
    )
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
        from app.services.object_storage import StorageError, UploadCategory, save_upload

        with pytest.raises(StorageError, match="Could not write the file to Backblaze B2"):
            save_upload(UploadCategory.DOCUMENTS, "spec.pdf", io.BytesIO(b"%PDF-1.4"))
        mock_s3.put_object.assert_called_once()
        _native.assert_called_once()


class ConnectionClosedError(Exception):
    """Stand-in for botocore.exceptions.ConnectionClosedError."""


@patch("app.services.object_storage._put_native_b2", side_effect=Exception("native fail"))
@patch("app.services.object_storage._s3_client")
def test_b2_put_connection_closed_without_working_path_raises_storage_error(
    mock_client_factory, _native, flask_app
):
    mock_s3 = MagicMock()
    mock_s3.put_object.side_effect = ConnectionClosedError(
        "Connection was closed before we received a valid response from endpoint URL: "
        '"https://s3.us-west-004.backblazeb2.com".'
    )
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
        from app.services.object_storage import StorageError, UploadCategory, save_upload

        with pytest.raises(StorageError, match="Could not write the file to Backblaze B2"):
            save_upload(UploadCategory.DOCUMENTS, "spec.pdf", io.BytesIO(b"%PDF-1.4"))
        mock_s3.put_object.assert_called_once()
        _native.assert_called_once()


@patch("app.services.object_storage._put_native_b2")
def test_b2_save_upload_calls_native_put(mock_native, flask_app):
    flask_app.config.update(
        {
            "B2_APPLICATION_KEY_ID": "k",
            "B2_APPLICATION_KEY": "s",
            "B2_BUCKET_NAME": "usis-bucket",
            "B2_ENDPOINT": "https://s3.us-west-004.backblazeb2.com",
            "B2_PREFIX": None,
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
        mock_native.assert_called_once()
        assert mock_native.call_args.args[0] == "drawings/id.pdf"
        assert mock_native.call_args.kwargs["content_type"] == "application/pdf"


@patch("app.services.object_storage._put_native_b2")
def test_b2_save_upload_mirrors_to_nas(mock_native, flask_app, tmp_path):
    flask_app.config.update(
        {
            "B2_APPLICATION_KEY_ID": "k",
            "B2_APPLICATION_KEY": "s",
            "B2_BUCKET_NAME": "usis-bucket",
            "B2_ENDPOINT": "https://s3.us-west-004.backblazeb2.com",
            "B2_PREFIX": "prod/usis-cm",
            "B2_MIRROR_ROOT": str(tmp_path),
        }
    )
    with flask_app.app_context():
        from app.services.object_storage import UploadCategory, save_upload

        sz = save_upload(
            UploadCategory.DRAWINGS,
            "24060/Architectural/Permit-Set/A1.pdf",
            io.BytesIO(b"mirror-me"),
        )
        assert sz == 9
        dest = tmp_path / "prod" / "usis-cm" / "drawings" / "24060" / "Architectural" / "Permit-Set" / "A1.pdf"
        assert dest.read_bytes() == b"mirror-me"


@patch("app.services.object_storage._get_native_b2", return_value=None)
@patch("app.services.object_storage._head_native_b2", return_value=None)
@patch("app.services.object_storage._s3_client")
def test_b2_enabled_does_not_read_nas(mock_client_factory, _head_native, _get_native, flask_app, tmp_path):
    """Website/API must not fall through to the NAS when B2 is configured."""
    mock_s3 = MagicMock()
    mock_s3.head_object.side_effect = Exception("SSL validation failed EOF")
    mock_s3.get_object.side_effect = Exception("SSL validation failed EOF")
    mock_client_factory.return_value = mock_s3
    rel = Path("24060") / "Architectural" / "Permit-Set" / "A1.pdf"
    dest = tmp_path / "prod" / "usis-cm" / "drawings" / rel
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"%PDF-1.4 nas")
    flask_app.config.update(
        {
            "B2_APPLICATION_KEY_ID": "k",
            "B2_APPLICATION_KEY": "s",
            "B2_BUCKET_NAME": "usis-bucket",
            "B2_ENDPOINT": "https://s3.us-west-004.backblazeb2.com",
            "B2_PREFIX": "prod/usis-cm",
            "B2_MIRROR_ROOT": str(tmp_path),
            "DRAWING_UPLOAD_FOLDER": str(tmp_path / "empty-instance"),
        }
    )
    with flask_app.app_context():
        from app.services.object_storage import (
            UploadCategory,
            read_first_stored,
            read_stored_bytes,
            send_stored_file,
            stored_exists,
            stored_size,
        )

        name = rel.as_posix()
        assert not stored_exists(UploadCategory.DRAWINGS, name)
        assert stored_size(UploadCategory.DRAWINGS, name) is None
        assert read_stored_bytes(UploadCategory.DRAWINGS, name) is None
        assert read_first_stored(UploadCategory.DRAWINGS, ["missing.pdf", name]) is None
        with flask_app.test_request_context():
            assert send_stored_file(
                UploadCategory.DRAWINGS,
                name,
                mimetype="application/pdf",
                download_name="A1.pdf",
            ) is None


@patch("app.services.object_storage._get_native_b2", return_value=b"%PDF-1.4 native")
@patch("app.services.object_storage._head_native_b2", return_value={"ContentLength": 16})
@patch("app.services.object_storage._s3_client")
def test_b2_read_falls_back_to_native_when_s3_drops(mock_client_factory, _head_native, _get_native, flask_app):
    """Files written via native B2 must still open when the S3 gateway is down."""
    mock_s3 = MagicMock()
    mock_s3.head_object.side_effect = Exception("SSL validation failed EOF")
    mock_s3.get_object.side_effect = Exception("SSL validation failed EOF")
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
        from app.services.object_storage import (
            UploadCategory,
            read_stored_bytes,
            send_stored_file,
            stored_exists,
            stored_size,
        )

        assert stored_exists(UploadCategory.DRAWINGS, "sheet.pdf")
        assert stored_size(UploadCategory.DRAWINGS, "sheet.pdf") == 16
        assert read_stored_bytes(UploadCategory.DRAWINGS, "sheet.pdf") == b"%PDF-1.4 native"
        with flask_app.test_request_context():
            resp = send_stored_file(
                UploadCategory.DRAWINGS,
                "sheet.pdf",
                mimetype="application/pdf",
                download_name="sheet.pdf",
            )
            assert resp is not None
            assert resp.get_data() == b"%PDF-1.4 native"


@patch("app.services.object_storage.time.sleep", return_value=None)
@patch("app.services.object_storage._b2_get_upload_url")
def test_native_upload_session_retries_then_succeeds(mock_get_url, _sleep, flask_app):
    mock_get_url.side_effect = [RuntimeError("b2 busy"), {"uploadUrl": "https://pod.example/up", "authorizationToken": "tok"}]
    flask_app.config.update(
        {
            "B2_APPLICATION_KEY_ID": "k",
            "B2_APPLICATION_KEY": "s",
            "B2_BUCKET_NAME": "usis-bucket",
            "B2_ENDPOINT": "https://s3.us-west-004.backblazeb2.com",
        }
    )
    with flask_app.app_context():
        from app.services.object_storage import UploadCategory, native_upload_session

        session = native_upload_session(UploadCategory.DRAWINGS, "sheet.pdf")
        assert session is not None
        assert session["mode"] == "b2_native"
        assert session["url"] == "https://pod.example/up"
        assert mock_get_url.call_count == 2
