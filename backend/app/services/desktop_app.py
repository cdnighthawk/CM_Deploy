"""Latest USISPdfApp Windows installer (GitHub Releases, optional local file)."""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import httpx

log = logging.getLogger(__name__)

DEFAULT_OWNER = "US-Interior-Specialties"
DEFAULT_REPO = "USIS_PDF_App"
GITHUB_API = "https://api.github.com"
USER_AGENT = "USIS-CM-desktop-app"
CACHE_TTL_SEC = 120
SETUP_NAME_RE = re.compile(r"^USIS-.+-Setup\.exe$", re.IGNORECASE)
VERSION_FROM_NAME_RE = re.compile(r"USIS-(.+)-Setup\.exe$", re.IGNORECASE)


@dataclass(frozen=True)
class DesktopSetup:
    version: str
    filename: str
    size: int | None
    source: str
    asset_id: int | None = None
    local_path: str | None = None
    html_url: str | None = None


class DesktopAppError(Exception):
    def __init__(self, message: str, status: int = 502):
        self.message = message
        self.status = status


_CACHE: dict[str, Any] = {"at": 0.0, "key": "", "item": None}


def _cfg(config: Any, key: str, default: str = "") -> str:
    if isinstance(config, dict):
        value = config.get(key, default)
    else:
        value = getattr(config, key, default)
    return str(value or default).strip()


def desktop_options(config: Any) -> dict[str, Any]:
    owner = _cfg(config, "GITHUB_DESKTOP_OWNER", DEFAULT_OWNER) or DEFAULT_OWNER
    repo = _cfg(config, "GITHUB_DESKTOP_REPO", DEFAULT_REPO) or DEFAULT_REPO
    token = _cfg(config, "GITHUB_DESKTOP_TOKEN") or _cfg(config, "GITHUB_FEEDBACK_TOKEN")
    local = _cfg(config, "GITHUB_DESKTOP_LOCAL_SETUP")
    return {
        "owner": owner,
        "repo": repo,
        "token": token,
        "local": local,
        "configured": bool(token or local),
    }


def pick_setup_asset(assets: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    """Choose the full Windows installer from a GitHub release asset list."""
    rows = [a for a in (assets or []) if isinstance(a, dict)]
    named = []
    for asset in rows:
        name = str(asset.get("name") or "").strip()
        if not name:
            continue
        named.append((name, asset))
    for name, asset in named:
        if SETUP_NAME_RE.match(name):
            return asset
    for name, asset in named:
        lower = name.lower()
        if lower.endswith(".exe") and "setup" in lower and "uninstall" not in lower:
            return asset
    return None


def version_from_setup_name(name: str, fallback: str = "") -> str:
    m = VERSION_FROM_NAME_RE.search((name or "").strip())
    if m:
        return m.group(1).strip()
    tag = (fallback or "").strip()
    return tag.lstrip("vV")


def _local_setup_path(raw: str) -> Path | None:
    if not raw:
        return None
    path = Path(raw)
    try:
        if path.is_file() and path.suffix.lower() == ".exe":
            return path
        if path.is_dir():
            cands = [
                p
                for p in path.glob("USIS-*-Setup.exe")
                if p.is_file()
            ]
            cands.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return cands[0] if cands else None
    except OSError:
        return None
    return None


def _github_headers(token: str, *, download: bool = False) -> dict[str, str]:
    headers = {
        "Accept": "application/octet-stream" if download else "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _latest_from_github(options: dict[str, Any], client: httpx.Client) -> DesktopSetup:
    owner = options["owner"]
    repo = options["repo"]
    token = options["token"]
    if not token:
        raise DesktopAppError(
            "Desktop app download is not configured. Set GITHUB_DESKTOP_TOKEN "
            "(Contents: Read on the USIS_PDF_App repo).",
            503,
        )
    url = f"{GITHUB_API}/repos/{owner}/{repo}/releases/latest"
    try:
        resp = client.get(url, headers=_github_headers(token), timeout=20.0)
    except httpx.HTTPError as exc:
        log.warning("GitHub latest-release request failed: %s", exc)
        raise DesktopAppError("Could not reach GitHub for the desktop installer.", 502) from exc
    if resp.status_code == 401:
        raise DesktopAppError("GitHub token was rejected. Check GITHUB_DESKTOP_TOKEN.", 502)
    if resp.status_code == 404:
        raise DesktopAppError(
            f"GitHub release not found for {owner}/{repo}. Check the repo name and token access.",
            502,
        )
    if resp.status_code >= 400:
        raise DesktopAppError(f"GitHub returned {resp.status_code} looking up the latest installer.", 502)
    try:
        payload = resp.json()
    except ValueError as exc:
        raise DesktopAppError("GitHub returned an unreadable release payload.", 502) from exc
    if not isinstance(payload, dict):
        raise DesktopAppError("GitHub returned an unreadable release payload.", 502)
    asset = pick_setup_asset(payload.get("assets") if isinstance(payload.get("assets"), list) else [])
    if not asset:
        raise DesktopAppError("The latest GitHub release does not include a Windows Setup.exe.", 502)
    filename = str(asset.get("name") or "").strip() or "USIS-Setup.exe"
    tag = str(payload.get("tag_name") or payload.get("name") or "").strip()
    try:
        asset_id = int(asset.get("id"))
    except (TypeError, ValueError) as exc:
        raise DesktopAppError("GitHub installer asset is missing an id.", 502) from exc
    size_raw = asset.get("size")
    try:
        size = int(size_raw) if size_raw is not None else None
    except (TypeError, ValueError):
        size = None
    html_url = str(payload.get("html_url") or "").strip() or None
    return DesktopSetup(
        version=version_from_setup_name(filename, tag),
        filename=filename,
        size=size,
        source="github",
        asset_id=asset_id,
        html_url=html_url,
    )


def _latest_from_local(local_raw: str) -> DesktopSetup:
    path = _local_setup_path(local_raw)
    if path is None:
        raise DesktopAppError("Local desktop installer path is missing or empty.", 503)
    return DesktopSetup(
        version=version_from_setup_name(path.name),
        filename=path.name,
        size=path.stat().st_size,
        source="local",
        local_path=str(path),
    )


def latest_setup(config: Any, client: httpx.Client | None = None, *, use_cache: bool = True) -> DesktopSetup:
    options = desktop_options(config)
    cache_key = f"{options['owner']}/{options['repo']}|{bool(options['token'])}|{options['local']}"
    now = time.monotonic()
    if (
        use_cache
        and _CACHE["item"] is not None
        and _CACHE["key"] == cache_key
        and (now - float(_CACHE["at"] or 0)) < CACHE_TTL_SEC
    ):
        return _CACHE["item"]

    item: DesktopSetup | None = None
    github_err: DesktopAppError | None = None
    if options["token"]:
        http = client or httpx.Client(timeout=20.0)
        close = client is None
        try:
            item = _latest_from_github(options, http)
        except DesktopAppError as exc:
            github_err = exc
        finally:
            if close:
                http.close()
    if item is None and options["local"]:
        try:
            item = _latest_from_local(options["local"])
        except DesktopAppError:
            if github_err:
                raise github_err
            raise
    if item is None:
        if github_err:
            raise github_err
        raise DesktopAppError(
            "Desktop app download is not configured. Set GITHUB_DESKTOP_TOKEN "
            "(Contents: Read on the USIS_PDF_App repo).",
            503,
        )
    _CACHE["at"] = now
    _CACHE["key"] = cache_key
    _CACHE["item"] = item
    return item


def setup_public(item: DesktopSetup) -> dict[str, Any]:
    return {
        "app": "USISPdfApp",
        "version": item.version,
        "filename": item.filename,
        "size": item.size,
        "source": item.source,
        "html_url": item.html_url,
        "download_path": "/api/v1/admin/desktop-app/download",
    }


def iter_github_asset(config: Any, item: DesktopSetup, client: httpx.Client | None = None) -> Iterator[bytes]:
    options = desktop_options(config)
    if not item.asset_id:
        raise DesktopAppError("Installer download is missing a GitHub asset id.", 502)
    url = f"{GITHUB_API}/repos/{options['owner']}/{options['repo']}/releases/assets/{item.asset_id}"
    headers = _github_headers(options["token"], download=True)
    http = client or httpx.Client(timeout=httpx.Timeout(30.0, read=300.0), follow_redirects=True)
    close = client is None
    try:
        with http.stream("GET", url, headers=headers) as resp:
            if resp.status_code >= 400:
                raise DesktopAppError(
                    f"GitHub returned {resp.status_code} downloading the installer.",
                    502,
                )
            for chunk in resp.iter_bytes(64 * 1024):
                if chunk:
                    yield chunk
    finally:
        if close:
            http.close()


def clear_cache() -> None:
    _CACHE["at"] = 0.0
    _CACHE["key"] = ""
    _CACHE["item"] = None
