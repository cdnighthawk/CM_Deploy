"""Oracle Textura Payment Management REST client (async export jobs + owner projects)."""
from __future__ import annotations

import base64
import logging
import re
import time
from typing import Any
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)

_JOB_ID_RE = re.compile(r"/(\d+)\s*$")


class TexturaClientError(RuntimeError):
    pass


class TexturaClient:
    """Thin httpx wrapper for TPM export/import job pattern."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        poll_interval_sec: float = 2.0,
        poll_timeout_sec: float = 300.0,
    ):
        self._base = base_url.rstrip("/")
        token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
        self._http = httpx.Client(
            base_url=self._base,
            headers={
                "Authentification": token,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )
        self._poll_interval = max(0.5, float(poll_interval_sec))
        self._poll_timeout = max(5.0, float(poll_timeout_sec))

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> TexturaClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def test_connection(self) -> None:
        """Lightweight call to verify credentials."""
        resp = self._http.get("/v2/owner/projects")
        resp.raise_for_status()

    def get_owner_projects(self) -> list[dict[str, Any]]:
        resp = self._http.get("/v2/owner/projects")
        resp.raise_for_status()
        return _normalize_record_list(resp.json())

    def export_invoices(self) -> list[dict[str, Any]]:
        job_path = self._start_export_job("/v1/export/invoices")
        payload = self._poll_job(job_path)
        return _normalize_record_list(payload)

    def _start_export_job(self, path: str) -> str:
        resp = self._http.post(path, json={})
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise TexturaClientError("export start response is not a JSON object")
        uri = data.get("URI") or data.get("uri")
        if isinstance(uri, str) and uri.strip():
            return _uri_to_job_path(uri.strip(), self._base)
        job_id = data.get("jobID") or data.get("jobId")
        if job_id is not None:
            return f"{path.rstrip('/')}/{job_id}"
        raise TexturaClientError("export start response missing URI or jobID")

    def _poll_job(self, job_path: str) -> Any:
        deadline = time.monotonic() + self._poll_timeout
        path = job_path if job_path.startswith("/") else f"/{job_path}"
        while time.monotonic() < deadline:
            resp = self._http.get(path)
            if resp.status_code == 202:
                time.sleep(self._poll_interval)
                continue
            resp.raise_for_status()
            return resp.json()
        raise TexturaClientError(f"Textura job timed out after {self._poll_timeout}s: {path}")


def _uri_to_job_path(uri: str, base_url: str) -> str:
    if uri.startswith("/"):
        return uri
    parsed = urlparse(uri)
    base_parsed = urlparse(base_url)
    if parsed.path:
        if parsed.netloc and parsed.netloc != base_parsed.netloc:
            return uri
        return parsed.path
    raise TexturaClientError(f"cannot parse job URI: {uri}")


def extract_job_id(job_path: str) -> str | None:
    m = _JOB_ID_RE.search(job_path.replace("\\", "/"))
    return m.group(1) if m else None


def _normalize_record_list(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []
    for key in (
        "projects",
        "Projects",
        "invoices",
        "Invoices",
        "records",
        "Records",
        "items",
        "Items",
        "data",
        "Data",
        "results",
        "Results",
    ):
        val = payload.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
    if any(k in payload for k in ("id", "projectName", "MainJobNumber", "DrawNumber")):
        return [payload]
    return []
