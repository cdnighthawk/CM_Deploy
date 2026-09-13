"""Field punch-list API: validation, local_id idempotency, GC create reject, notify flag."""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.extensions import db
from app.models import Contact, FieldPunchItem, Project, PunchNotifyLog


def _make_project() -> str:
    p = Project(name="Punch-" + uuid.uuid4().hex[:8])
    db.session.add(p)
    db.session.flush()
    pid = str(p.id)
    db.session.commit()
    return pid


def _payload(**overrides):
    body = {
        "local_id": str(uuid.uuid4()),
        "list": "ours",
        "title": "Corner bead crushed — Room 214",
        "description": None,
        "status": "open",
        "type": "damage",
        "priority": "blocking",
        "location_text": "Room 214",
        "trade": "drywall",
        "schedule_impact": "possible",
        "schedule_note": "Cannot tape until bead replaced",
        "cost_impact": "yes",
        "cost_note": "Will need extra bead + labor",
        "notify_on_save": False,
        "distribution": [],
    }
    body.update(overrides)
    return body


def test_create_requires_title(client):
    with client.application.app_context():
        pid = _make_project()
    r = client.post(f"/api/v1/projects/{pid}/punch-items", json=_payload(title=""))
    assert r.status_code == 400, r.get_data(as_text=True)
    body = r.get_json()
    assert body["field"] == "title"


def test_invalid_priority_names_field(client):
    with client.application.app_context():
        pid = _make_project()
    r = client.post(f"/api/v1/projects/{pid}/punch-items", json=_payload(priority="urgent"))
    assert r.status_code == 400
    assert r.get_json()["field"] == "priority"


def test_local_id_is_idempotent(client):
    with client.application.app_context():
        pid = _make_project()
    local = str(uuid.uuid4())
    first = client.post(f"/api/v1/projects/{pid}/punch-items", json=_payload(local_id=local))
    assert first.status_code == 201, first.get_data(as_text=True)
    item_id = first.get_json()["item"]["id"]
    second = client.post(f"/api/v1/projects/{pid}/punch-items", json=_payload(local_id=local, title="Retry title"))
    assert second.status_code == 200
    assert second.get_json()["item"]["id"] == item_id
    assert second.get_json()["item"]["title"] == "Corner bead crushed — Room 214"


def test_gc_create_rejected(client):
    with client.application.app_context():
        pid = _make_project()
    r = client.post(f"/api/v1/projects/{pid}/punch-items", json=_payload(list="gc"))
    assert r.status_code == 403
    assert r.get_json()["field"] == "list"


def test_notify_not_sent_when_flag_false(client, monkeypatch):
    sent = []

    def _fake_send(**kwargs):
        sent.append(kwargs)
        return {"sent": True, "dry_run": False, "error": None}

    monkeypatch.setattr("app.api._field_punch_service.send_html_notification_email", _fake_send)
    with client.application.app_context():
        pid = _make_project()
        contact = Contact(first_name="GC", last_name="Super", email="gc.super@example.com")
        db.session.add(contact)
        db.session.commit()
        cid = str(contact.id)

    r = client.post(
        f"/api/v1/projects/{pid}/punch-items",
        json=_payload(
            notify_on_save=False,
            distribution=[{"contact_id": cid, "email": "gc.super@example.com"}],
        ),
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    assert r.get_json()["item"]["last_notified_at"] is None
    assert sent == []
    with client.application.app_context():
        item_id = uuid.UUID(r.get_json()["item"]["id"])
        logs = list(db.session.scalars(select(PunchNotifyLog).where(PunchNotifyLog.punch_item_id == item_id)).all())
        assert logs == []


def test_notify_on_save_sends_one_per_contact(client, monkeypatch):
    sent = []

    def _fake_send(**kwargs):
        sent.append(kwargs["to"])
        return {"sent": True, "dry_run": False, "error": None}

    monkeypatch.setattr("app.api._field_punch_service.send_html_notification_email", _fake_send)
    with client.application.app_context():
        pid = _make_project()
        a = Contact(first_name="A", last_name="One", email="a@example.com")
        b = Contact(first_name="B", last_name="Two", email="b@example.com")
        db.session.add_all([a, b])
        db.session.commit()
        payload = _payload(
            notify_on_save=True,
            distribution=[
                {"contact_id": str(a.id), "email": "a@example.com"},
                {"contact_id": str(b.id), "email": "b@example.com"},
            ],
        )

    r = client.post(f"/api/v1/projects/{pid}/punch-items", json=payload)
    assert r.status_code == 201, r.get_data(as_text=True)
    assert sorted(sent) == ["a@example.com", "b@example.com"]
    item = r.get_json()["item"]
    assert item["last_notified_at"]
    with client.application.app_context():
        row = db.session.get(FieldPunchItem, uuid.UUID(item["id"]))
        assert row is not None
        logs = list(db.session.scalars(select(PunchNotifyLog).where(PunchNotifyLog.punch_item_id == row.id)).all())
        assert len(logs) == 1
        assert len(logs[0].recipients_json) == 2


def test_list_ours_and_empty_gc(client):
    with client.application.app_context():
        pid = _make_project()
    client.post(f"/api/v1/projects/{pid}/punch-items", json=_payload())
    ours = client.get(f"/api/v1/projects/{pid}/punch-items?list=ours")
    assert ours.status_code == 200
    assert ours.get_json()["ours_open"] == 1
    gc = client.get(f"/api/v1/projects/{pid}/punch-items?list=gc")
    assert gc.status_code == 200
    assert gc.get_json()["items"] == []


def test_directory_and_locations_empty_ok(client):
    with client.application.app_context():
        pid = _make_project()
    d = client.get(f"/api/v1/projects/{pid}/directory")
    assert d.status_code == 200
    assert d.get_json()["items"] == []
    loc = client.get(f"/api/v1/projects/{pid}/locations")
    assert loc.status_code == 200
    assert loc.get_json()["items"] == []


def test_create_without_local_id_and_room_alias(client):
    with client.application.app_context():
        pid = _make_project()
    r = client.post(
        f"/api/v1/projects/{pid}/punch-items",
        json={"title": "Web office item", "room": "Lobby"},
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    item = r.get_json()["item"]
    assert item["local_id"]
    assert item["location_text"] == "Lobby"
    got = client.get(f"/api/v1/punch-items/{item['id']}")
    assert got.status_code == 200
    assert got.get_json()["item"]["title"] == "Web office item"


def test_soft_delete_hides_item(client):
    with client.application.app_context():
        pid = _make_project()
    created = client.post(f"/api/v1/projects/{pid}/punch-items", json=_payload())
    item_id = created.get_json()["item"]["id"]
    gone = client.delete(f"/api/v1/punch-items/{item_id}")
    assert gone.status_code == 200
    listed = client.get(f"/api/v1/projects/{pid}/punch-items?list=ours")
    assert listed.get_json()["items"] == []
    assert client.get(f"/api/v1/punch-items/{item_id}").status_code == 404


def test_open_items_includes_field_crew_punch(client):
    with client.application.app_context():
        pid = _make_project()
    client.post(f"/api/v1/projects/{pid}/punch-items", json=_payload(title="Phone crush bead"))
    open_items = client.get(f"/api/v1/projects/{pid}/open-items")
    assert open_items.status_code == 200
    titles = {row["title"] for row in open_items.get_json()["items"]}
    assert "Phone crush bead" in titles
    kinds = {row["kind"] for row in open_items.get_json()["items"]}
    assert "crew_punch" in kinds


def _tiny_jpeg() -> bytes:
    return (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
        b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e"
        b"\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
        b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
        b"\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x08"
        b"\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00"
        b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\x7f\xff\xd9"
    )


def test_photo_ids_on_create_are_linked(client):
    import io

    with client.application.app_context():
        pid = _make_project()
    uploaded = client.post(
        f"/api/v1/projects/{pid}/photos",
        data={"file": (io.BytesIO(_tiny_jpeg()), "bead.jpg"), "album": "Punch"},
        content_type="multipart/form-data",
    )
    assert uploaded.status_code == 201, uploaded.get_data(as_text=True)
    photo_id = uploaded.get_json()["item"]["id"]
    created = client.post(
        f"/api/v1/projects/{pid}/punch-items",
        json=_payload(photo_ids=[photo_id]),
    )
    assert created.status_code == 201, created.get_data(as_text=True)
    photos = created.get_json()["item"]["photos"]
    assert len(photos) == 1
    assert photos[0]["id"] == photo_id


def test_orphan_punch_album_photo_is_claimed(client):
    import io

    with client.application.app_context():
        pid = _make_project()
    created = client.post(f"/api/v1/projects/{pid}/punch-items", json=_payload())
    assert created.status_code == 201
    item_id = created.get_json()["item"]["id"]
    uploaded = client.post(
        f"/api/v1/projects/{pid}/photos",
        data={"file": (io.BytesIO(_tiny_jpeg()), "bead.jpg"), "album": "Punch"},
        content_type="multipart/form-data",
    )
    assert uploaded.status_code == 201, uploaded.get_data(as_text=True)
    listed = client.get(f"/api/v1/projects/{pid}/punch-items?list=ours")
    assert listed.status_code == 200
    items = listed.get_json()["items"]
    assert items[0]["id"] == item_id
    assert len(items[0]["photos"]) == 1
    got = client.get(f"/api/v1/punch-items/{item_id}")
    assert len(got.get_json()["item"]["photos"]) == 1


def test_attach_photo_field_name(client):
    import io

    with client.application.app_context():
        pid = _make_project()
    created = client.post(f"/api/v1/projects/{pid}/punch-items", json=_payload())
    item_id = created.get_json()["item"]["id"]
    attached = client.post(
        f"/api/v1/punch-items/{item_id}/photos",
        data={"photo": (io.BytesIO(_tiny_jpeg()), "bead.jpg")},
        content_type="multipart/form-data",
    )
    assert attached.status_code == 201, attached.get_data(as_text=True)
    got = client.get(f"/api/v1/punch-items/{item_id}")
    assert len(got.get_json()["item"]["photos"]) == 1
    assert got.get_json()["item"]["photos"][0].get("data_url", "").startswith("data:image/")


def test_field_alias_photo_attach(client):
    import io

    with client.application.app_context():
        pid = _make_project()
    created = client.post(f"/api/field/projects/{pid}/punch-items", json=_payload())
    assert created.status_code == 201, created.get_data(as_text=True)
    item_id = created.get_json()["item"]["id"]
    attached = client.post(
        f"/api/field/punch-items/{item_id}/photos",
        data={"photo": (io.BytesIO(_tiny_jpeg()), "bead.jpg")},
        content_type="multipart/form-data",
    )
    assert attached.status_code == 201, attached.get_data(as_text=True)
    got = client.get(f"/api/field/punch-items/{item_id}")
    assert got.status_code == 200
    assert len(got.get_json()["item"]["photos"]) == 1


def test_inline_data_url_photo_on_create(client):
    import base64

    with client.application.app_context():
        pid = _make_project()
    jpeg = _tiny_jpeg()
    data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
    created = client.post(
        f"/api/v1/projects/{pid}/punch-items",
        json=_payload(photos=[{"data_url": data_url, "filename": "bead.jpg"}]),
    )
    assert created.status_code == 201, created.get_data(as_text=True)
    photos = created.get_json()["item"]["photos"]
    assert len(photos) == 1


def test_nearby_unlinked_photo_shown_on_detail(client):
    import io

    with client.application.app_context():
        pid = _make_project()
    created = client.post(f"/api/v1/projects/{pid}/punch-items", json=_payload())
    item_id = created.get_json()["item"]["id"]
    uploaded = client.post(
        f"/api/v1/projects/{pid}/photos",
        data={"file": (io.BytesIO(_tiny_jpeg()), "bead.jpg")},
        content_type="multipart/form-data",
    )
    assert uploaded.status_code == 201, uploaded.get_data(as_text=True)
    got = client.get(f"/api/v1/punch-items/{item_id}")
    assert len(got.get_json()["item"]["photos"]) >= 1
