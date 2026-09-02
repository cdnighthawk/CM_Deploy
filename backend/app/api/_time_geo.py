"""Project geofence: circle (haversine) or polygon (ray casting)."""
from __future__ import annotations

from typing import Any, Mapping

from ._time_clock_math import evaluate_geofence, haversine_m
from ..models.field_ops import DEFAULT_GEOFENCE_RADIUS_M


def _ring_from_geojson(raw: Mapping[str, Any] | list | None) -> list[tuple[float, float]]:
    if raw is None:
        return []
    coords: Any = raw
    if isinstance(raw, Mapping):
        geom = raw.get("geometry") if "geometry" in raw else raw
        if isinstance(geom, Mapping):
            coords = geom.get("coordinates")
        elif "coordinates" in raw:
            coords = raw.get("coordinates")
        elif "points" in raw:
            coords = raw.get("points")
    if not isinstance(coords, list) or not coords:
        return []
    ring = coords[0] if coords and isinstance(coords[0], list) and coords and isinstance(coords[0][0], (list, tuple)) else coords
    out: list[tuple[float, float]] = []
    for pt in ring:
        if not isinstance(pt, (list, tuple)) or len(pt) < 2:
            continue
        lon, lat = float(pt[0]), float(pt[1])
        out.append((lon, lat))
    return out


def point_in_ring(lon: float, lat: float, ring: list[tuple[float, float]]) -> bool:
    if len(ring) < 3:
        return False
    inside = False
    j = len(ring) - 1
    for i, (xi, yi) in enumerate(ring):
        xj, yj = ring[j]
        intersects = ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi)
        if intersects:
            inside = not inside
        j = i
    return inside


def evaluate_project_fence(
    *,
    fence: Any | None,
    project_lat: float | None,
    project_lon: float | None,
    project_radius_m: float | None,
    lat: float | None,
    lon: float | None,
    default_mode: str = "flag",
) -> tuple[bool | None, float | None, str]:
    """Return (inside_or_none, distance_m, mode). None inside = no fence configured."""
    mode = default_mode if default_mode in ("flag", "block") else "flag"
    if fence is not None:
        mode = str(getattr(fence, "mode", None) or mode).strip().lower() or mode
        shape = str(getattr(fence, "shape", None) or "circle").strip().lower()
        if shape == "polygon":
            ring = _ring_from_geojson(getattr(fence, "polygon_geojson", None))
            if lat is None or lon is None:
                return False, None, mode
            if not ring:
                return None, None, mode
            ok = point_in_ring(float(lon), float(lat), ring)
            dist = None
            clat = getattr(fence, "center_lat", None)
            clon = getattr(fence, "center_lon", None)
            if clat is not None and clon is not None:
                dist = haversine_m(float(clat), float(clon), float(lat), float(lon))
            return ok, dist, mode
        clat = getattr(fence, "center_lat", None)
        clon = getattr(fence, "center_lon", None)
        radius = getattr(fence, "radius_m", None)
        if clat is not None and clon is not None:
            ok, dist = evaluate_geofence(float(clat), float(clon), float(radius) if radius is not None else DEFAULT_GEOFENCE_RADIUS_M, lat, lon)
            return ok, dist, mode
    ok, dist = evaluate_geofence(project_lat, project_lon, project_radius_m, lat, lon)
    return ok, dist, mode
