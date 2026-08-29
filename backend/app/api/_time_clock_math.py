"""Pure helpers for field time-clock paid hours and geofence checks."""
from __future__ import annotations

import math
from datetime import datetime
from typing import Iterable, Mapping

from ..models.field_ops import DEFAULT_GEOFENCE_RADIUS_M

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    rlat1, rlon1, rlat2, rlon2 = (math.radians(lat1), math.radians(lon1), math.radians(lat2), math.radians(lon2))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def evaluate_geofence(
    project_lat: float | None,
    project_lon: float | None,
    radius_m: float | None,
    lat: float | None,
    lon: float | None,
) -> tuple[bool | None, float | None]:
    """Return (inside_or_none, distance_m). None/None when the project has no fence."""
    if project_lat is None or project_lon is None:
        return None, None
    radius = float(radius_m) if radius_m is not None else float(DEFAULT_GEOFENCE_RADIUS_M)
    if lat is None or lon is None:
        return False, None
    dist = haversine_m(float(project_lat), float(project_lon), float(lat), float(lon))
    return dist <= radius, dist


def paid_seconds(
    started_at: datetime,
    ended_at: datetime | None,
    punches: Iterable[Mapping[str, object]],
    now: datetime,
) -> float:
    """Paid time = shift length minus break intervals (open break counts through end/now)."""
    end = ended_at or now
    total = max(0.0, (end - started_at).total_seconds())
    events = sorted(
        punches,
        key=lambda p: p.get("occurred_at") or started_at,  # type: ignore[arg-type, return-value]
    )
    open_starts: list[datetime] = []
    break_secs = 0.0
    for ev in events:
        kind = str(ev.get("kind") or "")
        at = ev.get("occurred_at")
        if not isinstance(at, datetime):
            continue
        if kind == "break_start":
            open_starts.append(at)
        elif kind == "break_end" and open_starts:
            start = open_starts.pop(0)
            break_secs += max(0.0, (at - start).total_seconds())
    for start in open_starts:
        break_secs += max(0.0, (end - start).total_seconds())
    return max(0.0, total - break_secs)
