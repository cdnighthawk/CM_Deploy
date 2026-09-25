"""Tell the on-prem specialty-takeoff consumer that an estimate folder is ready.

CM on Render cannot write the office share or the Ingest drop folder. After
estimate-folder provision commits a non-empty ``folder_path`` with status
``ready``, provision calls :func:`on_estimate_folder_ready`. The default hook
best-effort POSTs ``usis.specialty_takeoff.v1`` to ``SPECIALTY_TAKEOFF_QUEUE_URL``
so the consumer can patch an existing queue job or create one. The on-prem
consumer owns dropping that JSON for the takeoff bots.

Unconfigured (URL unset) is a no-op. Failures are logged and never raised.
Swap the hook with :func:`set_on_estimate_folder_ready` or by replacing
``on_estimate_folder_ready`` on this module. See ``docs/specialty-takeoff-enqueue.md``.
"""
from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import current_app, has_app_context

logger = logging.getLogger(__name__)

SCHEMA = "usis.specialty_takeoff.v1"
STATUS_READY_FOR_TAKEOFF = "ready_for_takeoff"
QUEUE_HEADER = "X-USIS-Specialty-Takeoff-Token"
TAKEOFF_DIR = "03_Takeoff"
DEFAULT_TIMEOUT_SEC = 5.0

# Default nine CSI specialty slugs for USIS specialty takeoff bots.
# Eight are the product lines named for this queue; ``signage`` is CSI 10 14 00
# from the USIS estimating presets (alongside 10 11 markerboards, 10 21
# partitions, 10 26 wall protection, 10 28 accessories, 10 44 cabinets,
# 10 51 lockers, 06 40 millwork, and 08 doors). Override with
# SPECIALTY_TAKEOFF_SLUGS (comma-separated) without editing call sites.
SPECIALTY_SLUGS: tuple[str, ...] = (
    "bathroom_partitions",
    "bathroom_accessories",
    "lockers",
    "wall_protection",
    "fire_extinguisher_cabinets",
    "commercial_millwork",
    "doors",
    "markerboards",
    "signage",
)

_unconfigured_logged = False
FolderReadyHook = Callable[[Any, str], None]


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


def queue_url() -> str | None:
    raw = _cfg("SPECIALTY_TAKEOFF_QUEUE_URL")
    if raw is None:
        return None
    url = str(raw).strip()
    return url or None


def queue_token() -> str | None:
    raw = _cfg("SPECIALTY_TAKEOFF_QUEUE_TOKEN")
    if raw is None:
        return None
    token = str(raw).strip()
    return token or None


def queue_timeout_sec() -> float:
    raw = _cfg("SPECIALTY_TAKEOFF_QUEUE_TIMEOUT_SEC", DEFAULT_TIMEOUT_SEC)
    try:
        return max(1.0, min(float(raw), 30.0))
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_SEC


def specialty_slugs() -> tuple[str, ...]:
    """Nine default slugs, or ``SPECIALTY_TAKEOFF_SLUGS`` when that env is set."""
    raw = _cfg("SPECIALTY_TAKEOFF_SLUGS")
    if raw is None or str(raw).strip() == "":
        return SPECIALTY_SLUGS
    slugs = tuple(part.strip() for part in str(raw).split(",") if part.strip())
    return slugs or SPECIALTY_SLUGS


def artifact_root_for(folder_path: str, specialty: str) -> str:
    """Canonical drop path ``{folder_path}\\03_Takeoff\\{specialty}\\``.

    Uses the separator already in ``folder_path``. A provisioned Windows path
    stays Windows (``Y:\\Estimates\\{job} - {name}\\03_Takeoff\\{specialty}\\``).
    CM does not create these directories.
    """
    text = str(folder_path or "").strip().rstrip("/\\")
    slug = str(specialty or "").strip().strip("/\\")
    sep = "\\" if "\\" in text else "/"
    return f"{text}{sep}{TAKEOFF_DIR}{sep}{slug}{sep}"


def build_payload(estimate_id: Any, folder_path: str) -> dict[str, Any]:
    """JSON body for ``usis.specialty_takeoff.v1``. ``folder_path`` is stored verbatim.

    The consumer patches the queue job for ``estimate_id`` when one exists and
    creates it otherwise. ``artifact_roots`` is one canonical path per specialty.
    """
    path = str(folder_path)
    slugs = list(specialty_slugs())
    return {
        "schema": SCHEMA,
        "estimate_id": str(estimate_id),
        "folder_path": path,
        "status": STATUS_READY_FOR_TAKEOFF,
        "specialties": slugs,
        "artifact_roots": {slug: artifact_root_for(path, slug) for slug in slugs},
    }


def post_queue(url: str, payload: Mapping[str, Any], headers: dict[str, str], timeout: float) -> int:
    """POST JSON. Returns the HTTP status. Network errors propagate; HTTP errors return the code."""
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, method="POST", headers=headers)
    try:
        with urlopen(req, timeout=timeout) as resp:
            return int(getattr(resp, "status", 200) or 200)
    except HTTPError as exc:
        return int(exc.code)


def _http_on_estimate_folder_ready(estimate_id: Any, folder_path: str) -> None:
    """POST an upsert for this estimate. No-op when the queue URL is unset."""
    global _unconfigured_logged
    path = str(folder_path or "").strip()
    if not path:
        logger.warning(
            "specialty takeoff enqueue skipped (empty folder_path) estimate_id=%s",
            estimate_id,
        )
        return
    url = queue_url()
    if not url:
        if not _unconfigured_logged:
            logger.info(
                "specialty takeoff enqueue skipped (SPECIALTY_TAKEOFF_QUEUE_URL is not set) estimate_id=%s",
                estimate_id,
            )
            _unconfigured_logged = True
        else:
            logger.debug(
                "specialty takeoff enqueue skipped (SPECIALTY_TAKEOFF_QUEUE_URL is not set) estimate_id=%s",
                estimate_id,
            )
        return
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    token = queue_token()
    if token:
        headers[QUEUE_HEADER] = token
    payload = build_payload(estimate_id, path)
    status = post_queue(url, payload, headers, queue_timeout_sec())
    if status >= 400:
        logger.warning(
            "specialty takeoff enqueue HTTP %s estimate_id=%s",
            status,
            payload.get("estimate_id"),
        )
        return
    logger.info(
        "specialty takeoff enqueue posted estimate_id=%s http=%s",
        payload.get("estimate_id"),
        status,
    )


_registered_hook: FolderReadyHook = _http_on_estimate_folder_ready


def set_on_estimate_folder_ready(hook: FolderReadyHook | None) -> None:
    """Install a replacement for :func:`on_estimate_folder_ready`.

    Pass ``None`` to restore the default HTTP upsert. Tests can also replace
    ``on_estimate_folder_ready`` on this module; provision looks the name up
    at call time.
    """
    global _registered_hook
    _registered_hook = hook or _http_on_estimate_folder_ready


def on_estimate_folder_ready(estimate_id: Any, folder_path: str) -> None:
    """Folder-ready hook. Never raises.

    Default: patch-or-create semantics via HTTP POST of ``usis.specialty_takeoff.v1``
    when ``SPECIALTY_TAKEOFF_QUEUE_URL`` is set, otherwise a no-op. The consumer
    updates the existing specialty-takeoff job for ``estimate_id`` or creates one.
    """
    try:
        _registered_hook(estimate_id, folder_path)
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        logger.warning(
            "specialty takeoff enqueue failed estimate_id=%s error=%s",
            estimate_id,
            exc,
        )
    except Exception as exc:
        logger.warning(
            "specialty takeoff enqueue failed estimate_id=%s error=%s",
            estimate_id,
            exc,
        )
