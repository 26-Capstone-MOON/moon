"""OSM spatial-element collection through the Overpass API."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from constants import CATEGORY_P_VALUES
from geo import haversine
from poi_service import PoiResult, determine_position

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_RADIUS_M = 80
OVERPASS_QUERY_TIMEOUT_S = 2
OVERPASS_HTTP_TIMEOUT_S = 2.5
OVERPASS_RESULT_LIMIT = 30
OSM_CACHE_TTL_S = 120.0
OVERPASS_FAILURE_BACKOFF_S = 30.0

_CACHE: dict[tuple[float, float], tuple[float, list[dict[str, Any]]]] = {}
_unavailable_until = 0.0

OSM_CATEGORY_CODES: dict[str, str] = {
    "PARK": "OSM_PARK",
    "SQUARE": "OSM_SQUARE",
    "BRIDGE": "OSM_BRIDGE",
    "SUBWAY_ENTRANCE": "OSM_SUBWAY_ENTRANCE",
}

_PRESERVED_TAGS = {
    "name", "name:ko", "ref", "local_ref", "leisure", "place",
    "bridge", "man_made", "railway", "station", "station_name",
    "railway:station", "level", "layer",
}


def _build_query(lat: float, lon: float) -> str:
    around = f"around:{OVERPASS_RADIUS_M},{lat:.7f},{lon:.7f}"
    return (
        f"[out:json][timeout:{OVERPASS_QUERY_TIMEOUT_S}];"
        "("
        f'nwr({around})["leisure"="park"];'
        f'nwr({around})["place"="square"];'
        f'nwr({around})["bridge"="yes"];'
        f'nwr({around})["man_made"="bridge"];'
        f'nwr({around})["railway"="subway_entrance"];'
        ");"
        f"out center {OVERPASS_RESULT_LIMIT};"
    )


def _osm_type(tags: dict[str, Any]) -> str | None:
    if tags.get("railway") == "subway_entrance":
        return "SUBWAY_ENTRANCE"
    if tags.get("leisure") == "park":
        return "PARK"
    if tags.get("place") == "square":
        return "SQUARE"
    if tags.get("bridge") == "yes" or tags.get("man_made") == "bridge":
        return "BRIDGE"
    return None


def _display_name(tags: dict[str, Any], osm_type: str) -> str | None:
    for key in ("name:ko", "name"):
        value = tags.get(key)
        if value is not None and str(value).strip():
            name = str(value).strip()
            ref = tags.get("ref") or tags.get("local_ref")
            if osm_type == "SUBWAY_ENTRANCE" and ref and str(ref).strip() not in name:
                return f"{name} {str(ref).strip()}"
            return name

    ref = tags.get("ref") or tags.get("local_ref")
    if osm_type == "SUBWAY_ENTRANCE" and ref:
        for key in ("station_name", "railway:station", "station"):
            station = str(tags.get(key, "")).strip()
            if station and station.casefold() not in {"yes", "subway", "station"}:
                return f"{station} {str(ref).strip()}"
        return None
    if osm_type != "SUBWAY_ENTRANCE" and ref is not None and str(ref).strip():
        return str(ref).strip()
    return None


def _coordinates(element: dict[str, Any]) -> tuple[float, float] | None:
    lat = element.get("lat")
    lon = element.get("lon")
    if lat is None or lon is None:
        center = element.get("center") or {}
        lat = center.get("lat")
        lon = center.get("lon")
    try:
        lat_value = float(lat)
        lon_value = float(lon)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat_value <= 90 and -180 <= lon_value <= 180):
        return None
    return lat_value, lon_value


def normalize_osm_elements(
    elements: list[dict[str, Any]],
    dp_lat: float,
    dp_lon: float,
    travel_bearing: float,
) -> list[PoiResult]:
    """Normalize named/ref OSM node, way, and relation elements."""
    pois: list[PoiResult] = []
    seen: set[tuple[str, str]] = set()

    for element in elements[:OVERPASS_RESULT_LIMIT]:
        tags = element.get("tags") or {}
        osm_type = _osm_type(tags)
        name = _display_name(tags, osm_type) if osm_type else None
        coords = _coordinates(element)
        element_type = str(element.get("type", ""))
        element_id = element.get("id")
        if not osm_type or not name or not coords or element_type not in {
            "node", "way", "relation",
        } or element_id is None:
            continue

        osm_id = f"{element_type}/{element_id}"
        dedup_key = (osm_id, osm_type)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        poi_lat, poi_lon = coords
        distance = haversine(dp_lat, dp_lon, poi_lat, poi_lon)
        if distance > OVERPASS_RADIUS_M:
            continue
        category_code = OSM_CATEGORY_CODES[osm_type]
        preserved_tags = {
            str(key): str(value)
            for key, value in tags.items()
            if key in _PRESERVED_TAGS and value is not None
        }
        pois.append(PoiResult(
            place_name=name,
            category_group_code=category_code,
            category_name=f"OSM > {osm_type}",
            latitude=poi_lat,
            longitude=poi_lon,
            distance=distance,
            position=determine_position(
                dp_lat, dp_lon, poi_lat, poi_lon, travel_bearing,
            ),
            p_value=CATEGORY_P_VALUES[category_code],
            source="OSM",
            osm_type=osm_type,
            osm_id=osm_id,
            osm_tags=preserved_tags,
        ))

    counts: dict[str, int] = {}
    for poi in pois:
        counts[poi.category_group_code] = counts.get(poi.category_group_code, 0) + 1
    for poi in pois:
        poi.same_category_count_100m = counts[poi.category_group_code]
    pois.sort(key=lambda poi: poi.distance)
    return pois


async def search_osm_for_dp(
    lat: float,
    lon: float,
    travel_bearing: float,
) -> list[PoiResult]:
    """Fetch nearby OSM spatial elements; return an empty list on any failure."""
    global _unavailable_until

    cache_key = (round(lat, 5), round(lon, 5))
    now = time.monotonic()
    cached = _CACHE.get(cache_key)
    if cached and now - cached[0] < OSM_CACHE_TTL_S:
        return normalize_osm_elements(cached[1], lat, lon, travel_bearing)
    if now < _unavailable_until:
        return []

    try:
        async with asyncio.timeout(OVERPASS_HTTP_TIMEOUT_S):
            async with httpx.AsyncClient(timeout=OVERPASS_HTTP_TIMEOUT_S) as client:
                response = await client.post(
                    OVERPASS_URL,
                    data={"data": _build_query(lat, lon)},
                )
        response.raise_for_status()
        data = response.json()
        elements = data.get("elements", []) if isinstance(data, dict) else []
        if not isinstance(elements, list):
            return []
    except (TimeoutError, httpx.HTTPError, ValueError, TypeError):
        _unavailable_until = time.monotonic() + OVERPASS_FAILURE_BACKOFF_S
        return []

    _CACHE[cache_key] = (now, elements[:OVERPASS_RESULT_LIMIT])
    return normalize_osm_elements(elements, lat, lon, travel_bearing)
