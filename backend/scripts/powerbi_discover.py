"""List Power BI workspaces and reports for embed setup.

Requires in ``backend/.env`` (or environment):

- ``POWERBI_TENANT_ID``
- ``POWERBI_CLIENT_ID``
- ``POWERBI_CLIENT_SECRET``

Optional (validates access to one report):

- ``POWERBI_WORKSPACE_ID``
- ``POWERBI_REPORT_ID``

Usage (from ``backend/``):

    python scripts/powerbi_discover.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

_SCOPE = "https://analysis.windows.net/powerbi/api/.default"
_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
_API_BASE = "https://api.powerbi.com/v1.0/myorg"


def _load_dotenv() -> None:
    backend = Path(__file__).resolve().parents[1]
    env_path = backend / ".env"
    if env_path.is_file():
        load_dotenv(env_path)
    else:
        load_dotenv()


def _require(*keys: str) -> dict[str, str]:
    out: dict[str, str] = {}
    missing: list[str] = []
    for k in keys:
        v = (os.environ.get(k) or "").strip()
        if not v:
            missing.append(k)
        else:
            out[k] = v
    if missing:
        print("Missing environment variables:", ", ".join(missing), file=sys.stderr)
        print("See docs/powerbi-embed.md and backend/.env.example", file=sys.stderr)
        sys.exit(1)
    return out


def _aad_token(tenant: str, client_id: str, secret: str) -> str:
    url = _TOKEN_URL.format(tenant=tenant)
    with httpx.Client(timeout=45.0) as client:
        r = client.post(
            url,
            data={
                "client_id": client_id,
                "client_secret": secret,
                "scope": _SCOPE,
                "grant_type": "client_credentials",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if r.status_code != 200:
        print(f"Azure AD token failed ({r.status_code}):\n{r.text[:800]}", file=sys.stderr)
        sys.exit(1)
    tok = r.json().get("access_token")
    if not tok:
        print("Azure AD response missing access_token", file=sys.stderr)
        sys.exit(1)
    return str(tok)


def main() -> int:
    _load_dotenv()
    creds = _require("POWERBI_TENANT_ID", "POWERBI_CLIENT_ID", "POWERBI_CLIENT_SECRET")
    token = _aad_token(creds["POWERBI_TENANT_ID"], creds["POWERBI_CLIENT_ID"], creds["POWERBI_CLIENT_SECRET"])
    headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(timeout=60.0) as client:
        gr = client.get(f"{_API_BASE}/groups", headers=headers)
        if gr.status_code != 200:
            print(f"List workspaces failed ({gr.status_code}):\n{gr.text[:800]}", file=sys.stderr)
            return 1
        groups = gr.json().get("value") or []

    if not groups:
        print("No workspaces visible to this service principal.")
        print("Add the app to a workspace (Member/Admin) and enable SP APIs in Power BI admin settings.")
        return 1

    print("Workspaces and reports (copy ids into backend/.env):\n")
    for g in groups:
        wid = g.get("id", "")
        wname = g.get("name", "(unnamed)")
        print(f"WORKSPACE: {wname}")
        print(f"  POWERBI_WORKSPACE_ID={wid}")
        with httpx.Client(timeout=60.0) as client:
            rr = client.get(f"{_API_BASE}/groups/{wid}/reports", headers=headers)
        if rr.status_code != 200:
            print(f"  (list reports failed {rr.status_code}: {rr.text[:200]})")
            print()
            continue
        reports = rr.json().get("value") or []
        if not reports:
            print("  (no reports)")
        for rep in reports:
            rid = rep.get("id", "")
            rname = rep.get("name", "(unnamed)")
            print(f"  REPORT: {rname}")
            print(f"    POWERBI_REPORT_ID={rid}")
        print()

    ws = (os.environ.get("POWERBI_WORKSPACE_ID") or "").strip()
    rp = (os.environ.get("POWERBI_REPORT_ID") or "").strip()
    if ws and rp:
        with httpx.Client(timeout=60.0) as client:
            chk = client.get(f"{_API_BASE}/groups/{ws}/reports/{rp}", headers=headers)
        if chk.status_code == 200:
            body = chk.json()
            print("Configured report check: OK")
            print(f"  name: {body.get('name')}")
            print(f"  embedUrl: {body.get('embedUrl', '')[:80]}...")
        else:
            print(f"Configured report check failed ({chk.status_code}): {chk.text[:400]}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
