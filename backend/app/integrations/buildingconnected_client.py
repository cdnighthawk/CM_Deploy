"""BuildingConnected REST client (projects + Bid Board opportunities)."""
from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import Any

import httpx

log = logging.getLogger(__name__)

MAX_PAGES = 50


def next_cursor_state(payload: dict[str, Any]) -> str | None:
    """APS v2 returns ``pagination.cursorState``; some payloads also put it at the root."""
    pag = payload.get("pagination")
    if isinstance(pag, dict):
        nxt = pag.get("cursorState")
        if isinstance(nxt, str) and nxt.strip():
            return nxt
    nxt = payload.get("cursorState")
    return nxt if isinstance(nxt, str) and nxt.strip() else None


class BuildingConnectedClient:
    """BC v2 ``GET /projects`` and ``GET /opportunities`` with cursor pagination."""

    def __init__(self, access_token: str, base_url: str):
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=30.0,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> BuildingConnectedClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _parse_json(self, resp: httpx.Response) -> Any:
        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            return {"raw": (resp.text or "")[:2000]}

    def _get_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        resp = self._http.get(path, params=params)
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            body = (resp.text or "")[:500]
            log.warning("BuildingConnected %s HTTP %s: %s", path, resp.status_code, body)
            raise
        data = resp.json()
        if not isinstance(data, dict):
            raise ValueError(f"{path} response is not a JSON object")
        return data

    def get_opportunity(self, opportunity_id: str) -> dict[str, Any]:
        """GET /opportunities/{opportunityId}."""
        data = self._get_json(f"/opportunities/{opportunity_id}", {})
        return data

    def patch_opportunity(self, opportunity_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        """
        PATCH /opportunities/{opportunityId}

        Example — Will Not Bid:
            curl -X PATCH \\
              "$BUILDINGCONNECTED_API_BASE/opportunities/OPPORTUNITY_ID" \\
              -H "Authorization: Bearer $ACCESS_TOKEN" \\
              -H "Content-Type: application/json" \\
              -d '{"submissionState":"DECLINED"}'
        """
        if not opportunity_id:
            raise ValueError("opportunity_id is required")
        if not isinstance(patch, dict) or not patch:
            raise ValueError("PATCH body is required")
        path = f"/opportunities/{opportunity_id}"
        last_exc: httpx.HTTPStatusError | None = None
        for attempt in range(3):
            resp = self._http.patch(path, json=patch, headers={"Content-Type": "application/json"})
            body = self._parse_json(resp)
            log.info(
                "BuildingConnected PATCH opportunity id=%s status=%s request=%s response_keys=%s",
                opportunity_id,
                resp.status_code,
                patch,
                list(body.keys()) if isinstance(body, dict) else type(body).__name__,
            )
            if resp.status_code == 429 and attempt < 2:
                retry_after = resp.headers.get("Retry-After")
                try:
                    wait_s = min(30.0, float(retry_after)) if retry_after else 0.5 * (2**attempt)
                except ValueError:
                    wait_s = 0.5 * (2**attempt)
                log.warning("BuildingConnected PATCH rate-limited; retry in %ss", wait_s)
                resp.close()
                time.sleep(wait_s)
                continue
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                log.warning(
                    "BuildingConnected PATCH %s HTTP %s: %s",
                    path,
                    resp.status_code,
                    (resp.text or "")[:500],
                )
                raise
            if not isinstance(body, dict):
                raise ValueError(f"{path} response is not a JSON object")
            return body
        if last_exc:
            raise last_exc
        raise RuntimeError("BuildingConnected PATCH opportunity failed")

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
        return self._get_json("/projects", params)

    def get_opportunities_page(
        self,
        *,
        limit: int = 100,
        cursor_state: str | None = None,
        updated_at_range: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if cursor_state:
            params["cursorState"] = cursor_state
        if updated_at_range:
            params["filter[updatedAt]"] = updated_at_range
        return self._get_json("/opportunities", params)

    def _iter_paged(
        self,
        *,
        label: str,
        fetch_page,
        limit: int,
        max_pages: int = MAX_PAGES,
    ) -> Iterator[dict[str, Any]]:
        cursor: str | None = None
        seen_cursors: set[str] = set()
        pages = 0
        cap = max(1, int(max_pages))
        while True:
            pages += 1
            if pages > cap:
                log.warning("BuildingConnected %s hit page cap (%s); stopping", label, cap)
                break
            payload = fetch_page(limit=limit, cursor_state=cursor)
            results = payload.get("results")
            if not isinstance(results, list) or not results:
                break
            log.info("BuildingConnected %s page=%s n=%s", label, pages, len(results))
            for item in results:
                if isinstance(item, dict):
                    yield item
            if len(results) < limit:
                break
            nxt = next_cursor_state(payload)
            if not nxt or nxt in seen_cursors:
                break
            seen_cursors.add(nxt)
            cursor = nxt

    def iter_projects(self, *, limit: int = 100, include_closed: bool = True) -> Iterator[dict[str, Any]]:
        def fetch_page(*, limit: int, cursor_state: str | None):
            return self.get_projects_page(
                limit=limit, include_closed=include_closed, cursor_state=cursor_state
            )

        yield from self._iter_paged(label="projects", fetch_page=fetch_page, limit=limit)

    def iter_opportunities(
        self,
        *,
        limit: int = 100,
        updated_at_range: str | None = None,
        max_pages: int = MAX_PAGES,
    ) -> Iterator[dict[str, Any]]:
        def fetch_page(*, limit: int, cursor_state: str | None):
            return self.get_opportunities_page(
                limit=limit,
                cursor_state=cursor_state,
                updated_at_range=updated_at_range,
            )

        yield from self._iter_paged(
            label="opportunities", fetch_page=fetch_page, limit=limit, max_pages=max_pages
        )
