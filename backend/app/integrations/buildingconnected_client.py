"""BuildingConnected REST client (projects list with cursor pagination)."""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx


class BuildingConnectedClient:
    """Thin wrapper over BC v2 ``GET /projects`` with ``cursorState`` / ``limit``."""

    def __init__(self, access_token: str, base_url: str):
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=60.0,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> BuildingConnectedClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_projects_page(
        self,
        *,
        limit: int = 100,
        include_closed: bool = True,
        cursor_state: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if include_closed:
            params["includeClosed"] = "true"
        if cursor_state:
            params["cursorState"] = cursor_state
        resp = self._http.get("/projects", params=params)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise ValueError("projects response is not a JSON object")
        return data

    def iter_projects(self, *, limit: int = 100, include_closed: bool = True) -> Iterator[dict[str, Any]]:
        cursor: str | None = None
        while True:
            payload = self.get_projects_page(
                limit=limit, include_closed=include_closed, cursor_state=cursor
            )
            results = payload.get("results")
            if not isinstance(results, list):
                break
            for item in results:
                if isinstance(item, dict):
                    yield item
            nxt = payload.get("cursorState")
            cursor = nxt if isinstance(nxt, str) and nxt.strip() else None
            if not cursor:
                break
