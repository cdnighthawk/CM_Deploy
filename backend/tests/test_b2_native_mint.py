"""Native B2 mint — no S3 fallback (does not need the database)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.drawing_upload import _as_b2_native_hint, native_upload_hint_for_drawing


def test_as_b2_native_hint_rejects_s3_presigned_put():
    hint = _as_b2_native_hint(
        {
            "mode": "s3_presigned_put",
            "url": "https://s3.us-west-004.backblazeb2.com/bucket/key.pdf?X-Amz-Credential=AKIA",
        }
    )
    assert hint is None


def test_as_b2_native_hint_rejects_x_amz_even_if_mode_looks_native():
    hint = _as_b2_native_hint(
        {
            "mode": "b2_native",
            "url": "https://s3.us-west-004.backblazeb2.com/bucket/key.pdf?X-Amz-Signature=x",
        }
    )
    assert hint is None


def test_as_b2_native_hint_accepts_b2_upload_file():
    hint = _as_b2_native_hint(
        {
            "mode": "b2_native",
            "url": "https://pod-000-1001-00.backblaze.com/b2api/v2/b2_upload_file/...",
            "authorization": "tok",
            "file_name": "jobs/1/drawings/a.pdf",
        }
    )
    assert hint is not None
    assert hint["protocol"] == "b2-native"
    assert hint["kind"] == "b2-native"
    assert hint["uploadUrl"] == hint["url"]
    assert "b2_upload_file" in hint["uploadUrl"]
    assert hint["authorizationToken"] == "tok"
    assert "X-Amz-" not in hint["uploadUrl"]
    assert hint.get("presignedPut") is None


def test_as_b2_native_hint_accepts_missing_kind_when_url_is_native():
    hint = _as_b2_native_hint(
        {
            "url": "https://pod-000-1001-00.backblaze.com/b2api/v2/b2_upload_file/x",
            "authorization": "tok",
            "file_name": "a.pdf",
        }
    )
    assert hint is not None
    assert hint["protocol"] == "b2-native"


def test_native_upload_hint_does_not_call_s3_presign(flask_app):
    d = MagicMock()
    d.id = "11111111-1111-1111-1111-111111111111"
    with flask_app.app_context():
        with (
            patch(
                "app.services.drawing_upload.preferred_drawing_object_name",
                return_value="sheet.pdf",
            ),
            patch("app.services.object_storage.native_upload_session", return_value=None),
            patch("app.services.object_storage.presigned_put_url") as presign,
        ):
            hint = native_upload_hint_for_drawing(d)
            assert hint is None
            presign.assert_not_called()
