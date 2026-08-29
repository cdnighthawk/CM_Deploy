"""Turn chat attachments (uploaded files or public URLs) into Grok context."""
from __future__ import annotations

import base64
import ipaddress
import re
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

MAX_ATTACHMENTS = 4
MAX_FILE_BYTES = 6 * 1024 * 1024
MAX_TEXT_CHARS = 60_000
FETCH_TIMEOUT_SEC = 20.0

_IMAGE_TYPES = frozenset({"image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"})
_TEXT_TYPES = frozenset(
    {
        "text/plain",
        "text/csv",
        "text/markdown",
        "text/html",
        "application/json",
        "application/xml",
        "text/xml",
    }
)


class AttachmentError(Exception):
    def __init__(self, message: str, *, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def _safe_name(name: Any) -> str:
    raw = str(name or "attachment").strip() or "attachment"
    return re.sub(r"[^\w.\- ()]+", "_", raw)[:180]


def _is_public_http_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").strip().lower()
    if not host or host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except (ValueError, TypeError, IndexError):
            return False
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def _decode_data(raw: Any) -> bytes:
    if isinstance(raw, bytes):
        return raw
    s = str(raw or "").strip()
    if not s:
        return b""
    if "," in s and s.lower().startswith("data:"):
        s = s.split(",", 1)[1]
    try:
        return base64.b64decode(s, validate=False)
    except Exception as exc:
        raise AttachmentError("could not decode attachment data") from exc


def _html_to_text(html: str) -> str:
    cleaned = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", html)
    cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"&nbsp;", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _pdf_to_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
        from io import BytesIO

        reader = PdfReader(BytesIO(data))
        parts: list[str] = []
        for page in reader.pages[:40]:
            parts.append(page.extract_text() or "")
        return "\n".join(parts).strip()
    except Exception:
        return ""


def _guess_mime(name: str, mime: str, data: bytes) -> str:
    m = (mime or "").split(";")[0].strip().lower()
    if m:
        return m
    lower = name.lower()
    if lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".webp"):
        return "image/webp"
    if lower.endswith(".gif"):
        return "image/gif"
    if lower.endswith(".pdf"):
        return "application/pdf"
    if lower.endswith(".csv"):
        return "text/csv"
    if lower.endswith((".md", ".markdown")):
        return "text/markdown"
    if lower.endswith(".json"):
        return "application/json"
    if lower.endswith((".html", ".htm")):
        return "text/html"
    if data[:4] == b"%PDF":
        return "application/pdf"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return "application/octet-stream"


def _text_from_bytes(name: str, mime: str, data: bytes) -> str:
    if mime == "application/pdf" or name.lower().endswith(".pdf") or data[:4] == b"%PDF":
        return _pdf_to_text(data)
    if mime in _TEXT_TYPES or mime.startswith("text/") or name.lower().endswith((".txt", ".csv", ".md", ".json", ".xml")):
        if mime == "text/html":
            return _html_to_text(data.decode("utf-8", errors="replace"))
        return data.decode("utf-8", errors="replace")
    return ""


def _clip(text: str) -> str:
    t = (text or "").strip()
    if len(t) <= MAX_TEXT_CHARS:
        return t
    return t[:MAX_TEXT_CHARS] + "\n\n[truncated]"


def _image_part(url: str) -> dict[str, Any]:
    return {"type": "image_url", "image_url": {"url": url}}


def _fetch_url(url: str) -> tuple[str, bytes]:
    if not _is_public_http_url(url):
        raise AttachmentError("that link is not allowed (use a public http or https URL)")
    try:
        with httpx.Client(timeout=FETCH_TIMEOUT_SEC, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "USIS-CM-Assistant/1.0"})
    except httpx.TimeoutException as exc:
        raise AttachmentError("timed out fetching that link") from exc
    except httpx.HTTPError as exc:
        raise AttachmentError(f"could not fetch that link: {exc}") from exc
    if resp.status_code >= 400:
        raise AttachmentError(f"link returned HTTP {resp.status_code}")
    data = resp.content or b""
    if len(data) > MAX_FILE_BYTES:
        raise AttachmentError(f"link content is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB")
    ctype = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
    return ctype, data


def process_attachments(raw: Any) -> tuple[str, list[dict[str, Any]], list[dict[str, str]]]:
    """Return (extra_text, image_parts, summaries)."""
    if raw in (None, []):
        return "", [], []
    if not isinstance(raw, list):
        raise AttachmentError("attachments must be an array")
    if len(raw) > MAX_ATTACHMENTS:
        raise AttachmentError(f"at most {MAX_ATTACHMENTS} attachments per message")

    texts: list[str] = []
    images: list[dict[str, Any]] = []
    summaries: list[dict[str, str]] = []

    for item in raw:
        if not isinstance(item, dict):
            raise AttachmentError("each attachment must be an object")
        kind = str(item.get("kind") or "file").strip().lower()
        if kind == "url":
            url = str(item.get("url") or "").strip()
            if not url:
                raise AttachmentError("link is missing a URL")
            ctype, data = _fetch_url(url)
            name = _safe_name(item.get("name") or urlparse(url).path.rsplit("/", 1)[-1] or "link")
            mime = _guess_mime(name, ctype or str(item.get("mime") or ""), data)
            if mime in _IMAGE_TYPES:
                images.append(_image_part(url))
                summaries.append({"kind": "url", "name": name, "url": url})
                continue
            extracted = _text_from_bytes(name, mime, data)
            if not extracted:
                extracted = f"(Could not extract text from {name}. Content-Type: {mime or 'unknown'}.)"
            texts.append(f"--- Link: {url} ---\n{_clip(extracted)}")
            summaries.append({"kind": "url", "name": name, "url": url})
            continue

        name = _safe_name(item.get("name") or "file")
        data = _decode_data(item.get("data"))
        if not data:
            raise AttachmentError(f"{name} is empty")
        if len(data) > MAX_FILE_BYTES:
            raise AttachmentError(f"{name} is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB")
        mime = _guess_mime(name, str(item.get("mime") or ""), data)
        if mime in _IMAGE_TYPES:
            data_url = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
            images.append(_image_part(data_url))
            summaries.append({"kind": "file", "name": name})
            continue
        extracted = _text_from_bytes(name, mime, data)
        if not extracted:
            raise AttachmentError(
                f"{name} is not a supported file. Use images (JPG/PNG), PDF, or text (TXT/CSV/MD/JSON)."
            )
        texts.append(f"--- File: {name} ---\n{_clip(extracted)}")
        summaries.append({"kind": "file", "name": name})

    return "\n\n".join(texts), images, summaries


def merge_user_content(content: Any, extra_text: str, image_parts: list[dict[str, Any]]) -> Any:
    text = content if isinstance(content, str) else ("" if content is None else str(content))
    text = text.strip()
    if extra_text:
        text = (text + "\n\n" + extra_text).strip() if text else extra_text
    if not image_parts:
        return text
    if not text:
        text = "Please review the attached image(s)."
    return [{"type": "text", "text": text}, *image_parts]
