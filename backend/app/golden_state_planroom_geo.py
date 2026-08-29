"""Map Golden State listing city/county names to coordinates for office distance."""
from __future__ import annotations

import re
from typing import Any, Mapping

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^a-z0-9\s]")
_COUNTY_SUFFIX_RE = re.compile(r"\s+county$")

# City centers take precedence over county centroids when the listing name is both.
_CITIES: dict[str, tuple[float, float]] = {
    "anaheim": (33.8366, -117.9143),
    "brawley": (32.9787, -115.5303),
    "burbank": (34.1808, -118.3090),
    "calexico": (32.6789, -115.4989),
    "carlsbad": (33.1581, -117.3506),
    "chula vista": (32.6401, -117.0842),
    "corona": (33.8753, -117.5664),
    "coronado": (32.6859, -117.1831),
    "costa mesa": (33.6411, -117.9187),
    "el cajon": (32.7948, -116.9625),
    "el centro": (32.7920, -115.5631),
    "elk grove": (38.4088, -121.3716),
    "encinitas": (33.0370, -117.2920),
    "escondido": (33.1192, -117.0864),
    "folsom": (38.6780, -121.1760),
    "fontana": (34.0922, -117.4350),
    "fullerton": (33.8704, -117.9242),
    "garden grove": (33.7739, -117.9414),
    "glendale": (34.1425, -118.2551),
    "hemet": (33.7475, -116.9719),
    "huntington beach": (33.6595, -117.9988),
    "imperial beach": (32.5839, -117.1131),
    "indio": (33.7206, -116.2156),
    "irvine": (33.6846, -117.8265),
    "la mesa": (32.7678, -117.0231),
    "lemon grove": (32.7426, -117.0314),
    "long beach": (33.7701, -118.1937),
    "los angeles": (34.0522, -118.2437),
    "menifee": (33.6784, -117.1668),
    "moreno valley": (33.9425, -117.2297),
    "murrieta": (33.5539, -117.2139),
    "national city": (32.6781, -117.0992),
    "newport beach": (33.6189, -117.9298),
    "oceanside": (33.1959, -117.3795),
    "ontario": (34.0633, -117.6509),
    "orange": (33.7879, -117.8531),
    "palm springs": (33.8303, -116.5453),
    "pasadena": (34.1478, -118.1445),
    "perris": (33.7825, -117.2286),
    "poway": (32.9628, -117.0359),
    "rancho cucamonga": (34.1064, -117.5931),
    "redlands": (34.0556, -117.1825),
    "rialto": (34.1064, -117.3703),
    "riverside": (33.9533, -117.3962),
    "roseville": (38.7521, -121.2880),
    "sacramento": (38.5816, -121.4944),
    "san bernardino": (34.1083, -117.2898),
    "san diego": (32.7157, -117.1611),
    "san marcos": (33.1434, -117.1661),
    "santa ana": (33.7455, -117.8677),
    "santa monica": (34.0195, -118.4912),
    "santee": (32.8384, -116.9739),
    "temecula": (33.4936, -117.1484),
    "torrance": (33.8358, -118.3406),
    "victorville": (34.5361, -117.2928),
    "vista": (33.2000, -117.2425),
}

_COUNTIES: dict[str, tuple[float, float]] = {
    "alameda": (37.6017, -121.7195),
    "alpine": (38.5789, -119.8208),
    "amador": (38.3489, -120.7741),
    "butte": (39.6254, -121.6000),
    "calaveras": (38.1960, -120.6805),
    "colusa": (39.1775, -122.2370),
    "contra costa": (37.8534, -121.9018),
    "del norte": (41.7076, -123.9650),
    "el dorado": (38.7426, -120.4358),
    "fresno": (36.7378, -119.7871),
    "glenn": (39.5983, -122.3920),
    "humboldt": (40.7450, -123.8695),
    "imperial": (32.8473, -115.5694),
    "inyo": (36.5111, -117.4100),
    "kern": (35.3426, -118.7299),
    "kings": (36.0754, -119.8155),
    "lake": (39.1012, -122.7532),
    "lassen": (40.6730, -120.5940),
    "los angeles": (34.0522, -118.2437),
    "madera": (37.2519, -119.6963),
    "marin": (38.0834, -122.7633),
    "mariposa": (37.5816, -119.9056),
    "mendocino": (39.3070, -123.3920),
    "merced": (37.2010, -120.7120),
    "modoc": (41.5900, -120.7250),
    "mono": (37.9390, -118.8870),
    "monterey": (36.2400, -121.3100),
    "napa": (38.5025, -122.2654),
    "nevada": (39.3010, -120.7680),
    "orange": (33.7175, -117.8311),
    "placer": (39.0633, -120.7170),
    "plumas": (40.0030, -120.8240),
    "riverside": (33.7437, -116.9710),
    "sacramento": (38.4747, -121.3542),
    "san benito": (36.6050, -121.0750),
    "san bernardino": (34.9592, -116.4194),
    "san diego": (32.7157, -117.1611),
    "san francisco": (37.7749, -122.4194),
    "san joaquin": (37.9340, -121.2720),
    "san luis obispo": (35.3100, -120.4400),
    "san mateo": (37.4337, -122.4014),
    "santa barbara": (34.6110, -120.0180),
    "santa clara": (37.2210, -121.6900),
    "santa cruz": (37.0450, -122.0090),
    "shasta": (40.7638, -122.0400),
    "sierra": (39.5770, -120.5210),
    "siskiyou": (41.5930, -122.5400),
    "solano": (38.2676, -121.9390),
    "sonoma": (38.5280, -122.8860),
    "stanislaus": (37.5591, -120.9970),
    "sutter": (39.0340, -121.6940),
    "tehama": (40.1260, -122.2340),
    "trinity": (40.6500, -123.1130),
    "tulare": (36.2200, -118.8000),
    "tuolumne": (38.0270, -119.9550),
    "ventura": (34.3700, -119.1400),
    "yolo": (38.6820, -121.9010),
    "yuba": (39.2690, -121.3530),
}


def normalize_place(name: str | None) -> str:
    text = _WS_RE.sub(" ", str(name or "").strip().lower())
    text = _PUNCT_RE.sub("", text)
    text = _COUNTY_SUFFIX_RE.sub("", text).strip()
    return text


def coords_for_place(name: str | None) -> tuple[float, float] | None:
    key = normalize_place(name)
    if not key:
        return None
    return _CITIES.get(key) or _COUNTIES.get(key)


def coords_for_planroom_row(row: Any) -> tuple[float, float] | None:
    detail = row.detail if isinstance(getattr(row, "detail", None), Mapping) else {}
    if isinstance(detail, Mapping):
        for key in ("city", "county"):
            dest = coords_for_place(detail.get(key) if isinstance(detail.get(key), str) else None)
            if dest:
                return dest
    return coords_for_place(getattr(row, "location", None))
