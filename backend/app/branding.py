"""Product vs company chrome.

Staff, login, and public RFP surfaces use WorX CM. Company mail, hire
packets, and careers keep USIS plus the eagle.
"""
from __future__ import annotations

PRODUCT_NAME = "WorX CM"
COMPANY_SHORT = "USIS"
PRODUCT_ICON_PATH = "/assets/images/branding/worx-cm-icon.svg"
COMPANY_EAGLE_PATH = "/assets/images/branding/usis-eagle-logo.png"


def _origin(origin: str | None) -> str:
    return (origin or "").strip().rstrip("/")


def product_icon_url(origin: str | None) -> str:
    base = _origin(origin)
    return f"{base}{PRODUCT_ICON_PATH}" if base else PRODUCT_ICON_PATH


def company_eagle_url(origin: str | None) -> str:
    base = _origin(origin)
    return f"{base}{COMPANY_EAGLE_PATH}" if base else COMPANY_EAGLE_PATH


def company_email_header_html(origin: str | None) -> str:
    eagle = company_eagle_url(origin)
    return (
        "<div style='border-top:3px solid #C8102E;padding:12px 16px;"
        "font-family:Source Sans 3,system-ui,sans-serif'>"
        f"<img src='{eagle}' alt='USIS' width='40' height='40' "
        "style='vertical-align:middle;margin-right:10px;border:0'>"
        "<span style='font-weight:650;font-size:18px;color:#1E4B8F;"
        "vertical-align:middle'>USIS</span>"
        "</div>"
    )


def product_wordmark_html(*, icon_src: str = PRODUCT_ICON_PATH) -> str:
    return (
        f'<span class="d-inline-flex align-items-center gap-2">'
        f'<img src="{icon_src}" width="32" height="32" alt="" '
        f'style="border-radius:8px">'
        f'<strong class="usis-wordmark"><span class="usis-wordmark__worx">WorX</span> '
        f'<span class="usis-wordmark__cm">CM</span></strong></span>'
    )
