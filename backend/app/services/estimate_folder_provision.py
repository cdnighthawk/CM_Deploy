"""Provision a Windows-safe project folder tree when a CM estimate is created.

Production CM (Render) cannot write to the office ``Y:\\Estimates`` share.
The default path is an authenticated HTTP POST to an on-prem data-server agent.
``ESTIMATE_FOLDER_ROOT`` is a local/dev fallback that mkdirs only when that
path is writable.

Folder creation is best-effort: failures are logged and stored on the estimate
and never roll back the estimate row. See ``docs/estimate-folder-provision.md``.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import current_app, has_app_context
from sqlalchemy import event
from sqlalchemy.orm import Session, object_session

from ..extensions import db

logger = logging.getLogger(__name__)

PROVISION_HEADER = "X-USIS-Provision-Token"
PROVISION_PATH = "/provision/estimate-folder"
# Live agent (C:\\usis-cm\\folder_provision.py:5055) uses PROVISION_PATH.
# ESTIMATE_FOLDER_PROVISION_URL may be a base URL or the full path; these endings
# are treated as already-complete so the path is not appended twice.
PROVISION_PATH_ALIASES: frozenset[str] = frozenset(
    {
        "/provision/estimate-folder",
        "/provision/estimate-folders",
        "/estimate-folder",
    }
)
DEFAULT_TIMEOUT_SEC = 20.0
FOLDER_NAME_MAX = 150
STATUS_READY = "ready"
STATUS_FAILED = "failed"
STATUS_UNCONFIGURED = "unconfigured"

# Relative directories created under ``{root}/{job} - {name}/``.
FOLDER_TEMPLATE: tuple[str, ...] = (
    "01_Bid_Docs",
    "02_Processed",
    os.path.join("02_Processed", "drawings"),
    os.path.join("02_Processed", "specs"),
    os.path.join("02_Processed", "other"),
    "03_Takeoff",
    "04_Correspondence",
    "05_Reports",
)

README_NAME = "README.txt"
README_TEXT = """USIS CM estimate project folder

Created automatically when an estimate is created in CM. This tree is the
destination for BidDocProcessor / bid-doc copies and later CM ingest.

  01_Bid_Docs        Bid documents and BidDocProcessor copies
  02_Processed       Ingested files (drawings/, specs/, other/)
  03_Takeoff         Takeoff working files
  04_Correspondence  Email / Teams correspondence
  05_Reports         Estimate and bid reports

Do not rename the numbered folders. The estimate can be re-provisioned from
CM if this tree is missing (idempotent: existing folders are left in place).
"""

_WIN_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WIN_RESERVED = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)
_SESSION_QUEUE_KEY = "usis_estimate_folder_provision"
_SESSION_RUNNING_KEY = "usis_estimate_folder_provision_running"
_HOOKS_REGISTERED = False


@dataclass(frozen=True)
class ProvisionResult:
    ok: bool
    status: str
    path: str | None = None
    created: bool = False
    error: str | None = None
    via: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def sanitize_windows_folder_name(raw: str | None, *, fallback: str = "Estimate") -> str:
    """Return a single path segment that is safe on Windows NTFS / SMB."""
    text = str(raw or "").strip()
    text = _WIN_INVALID_CHARS.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if not text:
        text = fallback
    stem, dot, suffix = text.partition(".")
    check = (stem or text).upper()
    if check in _WIN_RESERVED:
        text = f"_{text}"
    if len(text) > FOLDER_NAME_MAX:
        text = text[:FOLDER_NAME_MAX].rstrip(" .")
    return text or fallback


def estimate_folder_name(job_or_id: str | None, name: str | None, *, estimate_id: uuid.UUID | str | None = None) -> str:
    """``{job_or_id} - {name}`` with Windows-safe segments."""
    fallback = str(estimate_id) if estimate_id is not None else "Estimate"
    job = sanitize_windows_folder_name(job_or_id, fallback=fallback)
    label = sanitize_windows_folder_name(name, fallback="Estimate")
    combined = f"{job} - {label}"
    if len(combined) > FOLDER_NAME_MAX:
        keep_job = min(len(job), 40)
        rest = FOLDER_NAME_MAX - keep_job - 3
        combined = f"{job[:keep_job]} - {label[: max(rest, 8)]}".rstrip(" .")
    return combined


def folder_template_relpaths() -> tuple[str, ...]:
    return FOLDER_TEMPLATE


def _cfg(name: str, default: Any = None) -> Any:
    if has_app_context() and name in current_app.config:
        val = current_app.config.get(name)
        if val is None or val == "":
            return default
        return val
    env = os.environ.get(name)
    if env is not None and str(env).strip() != "":
        return env
    return default


def provision_url() -> str | None:
    raw = _cfg("ESTIMATE_FOLDER_PROVISION_URL")
    if raw is None:
        return None
    url = str(raw).strip()
    return url or None


def resolve_provision_endpoint(url: str | None) -> str | None:
    """Build the POST URL. Accepts a base URL or a full/alias path."""
    raw = str(url or "").strip()
    if not raw:
        return None
    endpoint = raw.rstrip("/")
    if any(endpoint.endswith(alias) for alias in PROVISION_PATH_ALIASES):
        return endpoint
    return endpoint + PROVISION_PATH


def provision_token() -> str | None:
    raw = _cfg("ESTIMATE_FOLDER_PROVISION_TOKEN")
    if raw is None:
        return None
    token = str(raw).strip()
    return token or None


def provision_root() -> str | None:
    raw = _cfg("ESTIMATE_FOLDER_ROOT")
    if raw is None:
        return None
    root = str(raw).strip()
    return root or None


def provision_timeout_sec() -> float:
    raw = _cfg("ESTIMATE_FOLDER_PROVISION_TIMEOUT_SEC", DEFAULT_TIMEOUT_SEC)
    try:
        return max(1.0, min(float(raw), 120.0))
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_SEC


def is_configured() -> bool:
    return bool(provision_url() or provision_root())


def _estimate_session(est: Any):
    return object_session(est) or db.session


def job_number_for_estimate(est: Any) -> str:
    lead = getattr(est, "lead_estimate", None)
    if lead is not None:
        number = str(getattr(lead, "number", None) or "").strip()
        if number:
            return number
    project_id = getattr(est, "project_id", None)
    if project_id is not None:
        from ..models import Project

        project = _estimate_session(est).get(Project, project_id)
        if project is not None:
            number = str(getattr(project, "number", None) or "").strip()
            if number:
                return number
    return str(est.id)


def build_provision_payload(est: Any, *, requested_by: str | None = None) -> dict[str, Any]:
    lead = getattr(est, "lead_estimate", None)
    job_number = job_number_for_estimate(est)
    name = str(getattr(est, "name", None) or getattr(est, "title", None) or "Estimate").strip() or "Estimate"
    office = None
    if lead is not None:
        office = getattr(lead, "owning_office_id", None)
    return {
        "estimate_id": str(est.id),
        "job_number": job_number,
        "name": name,
        "project_uuid": str(est.project_id) if getattr(est, "project_id", None) else None,
        "requested_by": requested_by,
        "folder_name": estimate_folder_name(job_number, name, estimate_id=est.id),
        "office": str(office) if office else None,
        "lead_estimate_id": str(est.lead_estimate_id) if getattr(est, "lead_estimate_id", None) else None,
        "template": list(FOLDER_TEMPLATE),
    }


def apply_result_to_estimate(est: Any, result: ProvisionResult) -> None:
    est.folder_provision_status = result.status
    est.folder_path = result.path
    est.folder_provision_error = result.error
    if result.ok and result.status == STATUS_READY:
        est.folder_provisioned_at = datetime.now(timezone.utc)
    elif result.status == STATUS_FAILED:
        # Keep a previous success timestamp if the folder still exists.
        if not result.path:
            est.folder_provisioned_at = None


def create_local_folder_tree(root: str | Path, folder_name: str) -> tuple[str, bool]:
    """Create the template under ``root/folder_name``. Idempotent.

    Returns ``(absolute_path, created)`` where ``created`` is True when the
    project folder did not already exist.
    """
    root_path = Path(root)
    if not root_path.exists():
        raise OSError(f"ESTIMATE_FOLDER_ROOT does not exist: {root_path}")
    if not os.access(root_path, os.W_OK):
        raise OSError(f"ESTIMATE_FOLDER_ROOT is not writable: {root_path}")
    dest = root_path / folder_name
    created = not dest.exists()
    dest.mkdir(parents=True, exist_ok=True)
    for rel in FOLDER_TEMPLATE:
        (dest / rel).mkdir(parents=True, exist_ok=True)
    readme = dest / README_NAME
    if not readme.exists():
        readme.write_text(README_TEXT, encoding="utf-8")
    return str(dest.resolve()), created


def _http_post_json(url: str, payload: Mapping[str, Any], headers: dict[str, str], timeout: float) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, method="POST", headers=headers)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            status = int(getattr(resp, "status", 200) or 200)
    except HTTPError as exc:
        raw = exc.read() if exc.fp is not None else b""
        status = int(exc.code)
        try:
            parsed = json.loads(raw.decode("utf-8") or "{}") if raw else {}
        except json.JSONDecodeError:
            parsed = {"error": raw.decode("utf-8", errors="replace")[:500]}
        if not isinstance(parsed, dict):
            parsed = {"error": "invalid JSON error body"}
        return status, parsed
    try:
        parsed = json.loads(raw.decode("utf-8") or "{}") if raw else {}
    except json.JSONDecodeError as exc:
        raise ValueError(f"provisioner returned non-JSON body: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("provisioner JSON must be an object")
    return status, parsed


def _post_to_agent(payload: Mapping[str, Any]) -> ProvisionResult:
    url = provision_url()
    if not url:
        return ProvisionResult(ok=False, status=STATUS_UNCONFIGURED, error="ESTIMATE_FOLDER_PROVISION_URL is not set")
    endpoint = resolve_provision_endpoint(url)
    if not endpoint:
        return ProvisionResult(ok=False, status=STATUS_UNCONFIGURED, error="ESTIMATE_FOLDER_PROVISION_URL is not set")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    token = provision_token()
    if token:
        headers[PROVISION_HEADER] = token
    try:
        status, data = _http_post_json(endpoint, payload, headers, provision_timeout_sec())
    except (URLError, TimeoutError, ValueError, OSError) as exc:
        logger.error("estimate folder provision HTTP failed estimate_id=%s error=%s", payload.get("estimate_id"), exc)
        return ProvisionResult(ok=False, status=STATUS_FAILED, error=str(exc)[:1000], via="http")
    if status >= 400 or not data.get("ok"):
        err = str(data.get("error") or data.get("message") or f"provisioner HTTP {status}")[:1000]
        logger.error(
            "estimate folder provision rejected estimate_id=%s status=%s error=%s",
            payload.get("estimate_id"),
            status,
            err,
        )
        return ProvisionResult(ok=False, status=STATUS_FAILED, error=err, via="http", path=data.get("path"))
    path = data.get("path")
    path_s = str(path).strip() if path else None
    created = bool(data.get("created"))
    return ProvisionResult(ok=True, status=STATUS_READY, path=path_s, created=created, via="http")


def _mkdir_local(payload: Mapping[str, Any]) -> ProvisionResult:
    root = provision_root()
    if not root:
        return ProvisionResult(ok=False, status=STATUS_UNCONFIGURED, error="ESTIMATE_FOLDER_ROOT is not set")
    folder_name = str(payload.get("folder_name") or estimate_folder_name(payload.get("job_number"), payload.get("name")))
    try:
        path, created = create_local_folder_tree(root, folder_name)
    except OSError as exc:
        logger.error("estimate folder provision mkdir failed estimate_id=%s error=%s", payload.get("estimate_id"), exc)
        return ProvisionResult(ok=False, status=STATUS_FAILED, error=str(exc)[:1000], via="mkdir")
    return ProvisionResult(ok=True, status=STATUS_READY, path=path, created=created, via="mkdir")


def provision_estimate_folder(
    est: Any,
    *,
    requested_by: str | None = None,
) -> ProvisionResult:
    """Call the configured provisioner. Never raises."""
    payload = build_provision_payload(est, requested_by=requested_by)
    url = provision_url()
    root = provision_root()
    if not url and not root:
        logger.info(
            "estimate folder provision skipped (set ESTIMATE_FOLDER_PROVISION_URL or ESTIMATE_FOLDER_ROOT) estimate_id=%s",
            payload["estimate_id"],
        )
        return ProvisionResult(ok=True, status=STATUS_UNCONFIGURED, via=None)
    if url:
        result = _post_to_agent(payload)
        if result.ok or not root:
            return result
        logger.warning(
            "estimate folder provision HTTP failed; trying ESTIMATE_FOLDER_ROOT estimate_id=%s error=%s",
            payload["estimate_id"],
            result.error,
        )
    return _mkdir_local(payload)


def provision_estimate_folder_by_id(
    estimate_id: uuid.UUID | str,
    *,
    requested_by: str | None = None,
    persist: bool = True,
) -> ProvisionResult:
    """Load an estimate, provision, optionally persist status. Never raises.

    Persistence uses a standalone session so this is safe from SQLAlchemy
    ``after_commit`` (the request session is already in the committed state).
    """
    try:
        eid = estimate_id if isinstance(estimate_id, uuid.UUID) else uuid.UUID(str(estimate_id))
    except (TypeError, ValueError):
        return ProvisionResult(ok=False, status=STATUS_FAILED, error="invalid estimate id")
    from ..models import Estimate

    result: ProvisionResult | None = None
    try:
        with Session(bind=db.engine) as session:
            est = session.get(Estimate, eid)
            if est is None:
                logger.error("estimate folder provision: estimate not found id=%s", eid)
                return ProvisionResult(ok=False, status=STATUS_FAILED, error="estimate not found")
            result = provision_estimate_folder(est, requested_by=requested_by)
            if persist and result.status != STATUS_UNCONFIGURED:
                apply_result_to_estimate(est, result)
                session.commit()
    except Exception:
        logger.exception("estimate folder provision could not persist status estimate_id=%s", eid)
        if result is None:
            return ProvisionResult(ok=False, status=STATUS_FAILED, error="provision persist failed")
    _expire_cached_estimate(eid)
    return result or ProvisionResult(ok=False, status=STATUS_FAILED, error="provision failed")


def _expire_cached_estimate(estimate_id: uuid.UUID) -> None:
    """Drop a stale identity-map copy so the request session reloads status."""
    try:
        from ..models import Estimate

        for obj in list(db.session.identity_map.values()):
            if isinstance(obj, Estimate) and obj.id == estimate_id:
                db.session.expire(obj)
    except Exception:
        pass


def schedule_estimate_folder_provision(
    estimate_id: uuid.UUID,
    *,
    requested_by: str | None = None,
) -> None:
    """Queue provision to run after the current DB transaction commits."""
    info = db.session.info
    queue: list[dict[str, Any]] = info.setdefault(_SESSION_QUEUE_KEY, [])
    for item in queue:
        if item.get("estimate_id") == estimate_id:
            if requested_by and not item.get("requested_by"):
                item["requested_by"] = requested_by
            return
    queue.append({"estimate_id": estimate_id, "requested_by": requested_by})


def requested_by_label(user_id: uuid.UUID | None = None, email: str | None = None) -> str | None:
    if email:
        return str(email).strip() or None
    if user_id is None:
        return None
    from ..models import User

    user = db.session.get(User, user_id)
    if user is None:
        return str(user_id)
    return (user.email or "").strip() or str(user_id)


def _on_after_commit(session: Session) -> None:
    queue = list(session.info.pop(_SESSION_QUEUE_KEY, []) or [])
    if not queue or session.info.get(_SESSION_RUNNING_KEY):
        return
    from ..config import running_on_render

    def _run_queue() -> None:
        for item in queue:
            eid = item.get("estimate_id")
            if eid is None:
                continue
            try:
                provision_estimate_folder_by_id(eid, requested_by=item.get("requested_by"), persist=True)
            except Exception:
                logger.exception("estimate folder provision crashed estimate_id=%s", eid)

    # On Render, a 20s HTTP timeout to the office agent would block the only
    # gunicorn worker and fail /healthz. Local/tests stay synchronous so create
    # responses include folder_provision_status.
    if running_on_render():
        app = current_app._get_current_object() if has_app_context() else None

        def _run() -> None:
            if app is None:
                _run_queue()
                return
            with app.app_context():
                _run_queue()

        threading.Thread(target=_run, name="estimate-folder-provision", daemon=True).start()
        return
    session.info[_SESSION_RUNNING_KEY] = True
    try:
        _run_queue()
    finally:
        session.info.pop(_SESSION_RUNNING_KEY, None)


def _on_after_rollback(session: Session) -> None:
    session.info.pop(_SESSION_QUEUE_KEY, None)


def register_session_hooks() -> None:
    global _HOOKS_REGISTERED
    if _HOOKS_REGISTERED:
        return
    event.listen(Session, "after_commit", _on_after_commit)
    event.listen(Session, "after_rollback", _on_after_rollback)
    _HOOKS_REGISTERED = True


register_session_hooks()
