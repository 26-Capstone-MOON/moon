"""STEP 3: POI collection via Kakao Local API with adaptive radius."""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field

import httpx

from config import settings
from constants import (
    CATEGORY_P_VALUES,
    DEFAULT_P_VALUE,
    DEFAULT_POI_RADIUS,
    MAX_SEARCH_RADIUS,
    POI_RADIUS_EXPAND_1,
    POI_RADIUS_SHRINK,
)
from geo import calculate_bearing, haversine

KAKAO_CATEGORY_URL = "https://dapi.kakao.com/v2/local/search/category"
KAKAO_TIMEOUT = 5.0
BEARING_UNSTABLE_DISTANCE = 2.0  # meters — too close for reliable bearing
CROSSWALK_AFTER_OFFSET_M = 30.0  # meters past crosswalk for after-crossing POI search


@dataclass
class PoiResult:
    """A single POI from Kakao Local API with position and scoring info."""

    place_name: str
    category_group_code: str
    category_name: str
    latitude: float
    longitude: float
    distance: float  # meters from search center
    position: str  # LEFT | RIGHT | FRONT
    p_value: float  # base P from CATEGORY_P_VALUES
    same_category_count_100m: int | None = None


@dataclass
class CrosswalkPoiResult:
    """POI results for a crosswalk DP: before-crossing + after-crossing."""

    before: list[PoiResult] = field(default_factory=list)
    after: list[PoiResult] = field(default_factory=list)


def determine_position(
    dp_lat: float,
    dp_lon: float,
    poi_lat: float,
    poi_lon: float,
    travel_bearing: float,
) -> str:
    """Determine if POI is LEFT, RIGHT, or FRONT relative to travel direction.

    Args:
        dp_lat: DP latitude
        dp_lon: DP longitude
        poi_lat: POI latitude
        poi_lon: POI longitude
        travel_bearing: Travel direction in degrees (0~360)

    Returns:
        "LEFT", "RIGHT", or "FRONT"
    """
    dist = haversine(dp_lat, dp_lon, poi_lat, poi_lon)
    if dist < BEARING_UNSTABLE_DISTANCE:
        return "FRONT"

    poi_bearing = calculate_bearing(dp_lat, dp_lon, poi_lat, poi_lon)
    angle_diff = (poi_bearing - travel_bearing + 360) % 360

    if angle_diff < 30 or angle_diff > 330:
        return "FRONT"
    elif angle_diff <= 180:
        return "RIGHT"
    else:
        return "LEFT"


async def _kakao_category_search(
    client: httpx.AsyncClient,
    lat: float,
    lon: float,
    category_code: str,
    radius: int,
) -> list[dict]:
    """Call Kakao Local category search API for a single category.

    Args:
        client: Shared httpx async client
        lat: Search center latitude
        lon: Search center longitude
        category_code: Kakao category_group_code (e.g. "CS2")
        radius: Search radius in meters

    Returns:
        List of Kakao document dicts. Empty list on API failure.
    """
    headers = {"Authorization": f"KakaoAK {settings.kakao_api_key}"}
    params = {
        "category_group_code": category_code,
        "x": str(lon),
        "y": str(lat),
        "radius": str(radius),
        "sort": "distance",
    }
    try:
        resp = await client.get(KAKAO_CATEGORY_URL, headers=headers, params=params)
    except (httpx.TimeoutException, httpx.RequestError):
        return []

    if resp.status_code != 200:
        return []

    data = resp.json()
    return data.get("documents", [])


async def _search_all_categories(
    client: httpx.AsyncClient,
    lat: float,
    lon: float,
    radius: int,
) -> list[dict]:
    """Search all 18 Kakao category codes in parallel.

    Args:
        client: Shared httpx async client
        lat: Search center latitude
        lon: Search center longitude
        radius: Search radius in meters

    Returns:
        Aggregated list of document dicts from all categories.
    """
    categories = list(CATEGORY_P_VALUES.keys())
    tasks = [
        _kakao_category_search(client, lat, lon, cat, radius)
        for cat in categories
    ]
    results = await asyncio.gather(*tasks)

    all_docs: list[dict] = []
    for docs in results:
        all_docs.extend(docs)
    return all_docs


def _poi_dedup_key(
    place_name: str,
    latitude: float,
    longitude: float,
) -> tuple[str, float, float]:
    return place_name, round(latitude, 6), round(longitude, 6)


def _build_same_category_counts(
    docs: list[dict],
    center_lat: float,
    center_lon: float,
) -> dict[tuple[str, float, float], int]:
    """Count same-category POIs within the fixed 100m scoring radius."""
    deduped: dict[tuple[str, float, float], str] = {}

    for doc in docs:
        place_name = doc.get("place_name", "")
        poi_lat = float(doc.get("y", 0))
        poi_lon = float(doc.get("x", 0))
        if haversine(center_lat, center_lon, poi_lat, poi_lon) > MAX_SEARCH_RADIUS:
            continue

        deduped[_poi_dedup_key(place_name, poi_lat, poi_lon)] = doc.get(
            "category_group_code", "",
        )

    category_counts: dict[str, int] = {}
    for category_code in deduped.values():
        category_counts[category_code] = category_counts.get(category_code, 0) + 1

    return {
        key: category_counts.get(category_code, 1)
        for key, category_code in deduped.items()
    }


def _build_poi_results(
    docs: list[dict],
    center_lat: float,
    center_lon: float,
    travel_bearing: float,
    same_category_counts_100m: dict[tuple[str, float, float], int] | None = None,
) -> list[PoiResult]:
    """Convert raw Kakao docs into deduplicated PoiResult objects."""
    seen: set[tuple[str, float, float]] = set()
    pois: list[PoiResult] = []

    for doc in docs:
        place_name = doc.get("place_name", "")
        poi_lat = float(doc.get("y", 0))
        poi_lon = float(doc.get("x", 0))
        key = _poi_dedup_key(place_name, poi_lat, poi_lon)

        if key in seen:
            continue
        seen.add(key)

        cat_code = doc.get("category_group_code", "")
        distance = haversine(center_lat, center_lon, poi_lat, poi_lon)
        if distance > MAX_SEARCH_RADIUS:
            continue

        position = determine_position(
            center_lat, center_lon, poi_lat, poi_lon, travel_bearing,
        )
        p_value = CATEGORY_P_VALUES.get(cat_code, DEFAULT_P_VALUE)

        pois.append(PoiResult(
            place_name=place_name,
            category_group_code=cat_code,
            category_name=doc.get("category_name", ""),
            latitude=poi_lat,
            longitude=poi_lon,
            distance=distance,
            position=position,
            p_value=p_value,
            same_category_count_100m=(
                same_category_counts_100m.get(key)
                if same_category_counts_100m is not None
                else None
            ),
        ))

    pois.sort(key=lambda p: p.distance)
    return pois


async def search_pois_for_dp(
    lat: float,
    lon: float,
    travel_bearing: float,
) -> list[PoiResult]:
    """Search POIs near a DP with adaptive radius.

    Searches all 18 Kakao category codes in parallel. Applies adaptive
    radius logic: expands if 0 results, shrinks if 10+ results.

    Args:
        lat: DP latitude
        lon: DP longitude
        travel_bearing: Travel direction at DP in degrees (0~360)

    Returns:
        List of PoiResult sorted by distance ascending.
        Empty list if API key missing or all searches fail.
    """
    if not settings.kakao_api_key:
        return []

    async with httpx.AsyncClient(timeout=KAKAO_TIMEOUT) as client:
        # First pass with default radius
        all_docs = await _search_all_categories(
            client, lat, lon, int(DEFAULT_POI_RADIUS),
        )
        candidate_radius = int(DEFAULT_POI_RADIUS)

        # Adaptive radius
        if len(all_docs) == 0:
            all_docs = await _search_all_categories(
                client, lat, lon, int(POI_RADIUS_EXPAND_1),
            )
            candidate_radius = int(POI_RADIUS_EXPAND_1)
        elif len(all_docs) >= 20:
            all_docs = await _search_all_categories(
                client, lat, lon, int(POI_RADIUS_SHRINK),
            )
            candidate_radius = int(POI_RADIUS_SHRINK)

        uniqueness_docs = all_docs
        if candidate_radius != int(MAX_SEARCH_RADIUS):
            uniqueness_docs = await _search_all_categories(
                client, lat, lon, int(MAX_SEARCH_RADIUS),
            )

    same_category_counts_100m = _build_same_category_counts(
        uniqueness_docs, lat, lon,
    )
    return _build_poi_results(
        all_docs,
        lat,
        lon,
        travel_bearing,
        same_category_counts_100m,
    )


def _offset_point(lat: float, lon: float, bearing_deg: float, distance_m: float) -> tuple[float, float]:
    """Return (lat, lon) offset from a point along a bearing by distance_m meters."""
    rad = math.radians(bearing_deg)
    north_m = math.cos(rad) * distance_m
    east_m = math.sin(rad) * distance_m
    new_lat = lat + north_m / 111_111.0
    cos_lat = math.cos(math.radians(lat))
    new_lon = lon + east_m / (111_111.0 * cos_lat) if abs(cos_lat) > 1e-9 else lon
    return new_lat, new_lon


async def search_pois_for_crosswalk(
    lat: float,
    lon: float,
    travel_bearing: float,
) -> CrosswalkPoiResult:
    """Search POIs on both sides of a crosswalk DP.

    Before-crossing: POIs near the DP location (location assist).
    After-crossing: POIs ~30m ahead along travel bearing (direction target).

    Args:
        lat: Crosswalk DP latitude
        lon: Crosswalk DP longitude
        travel_bearing: Travel direction at DP in degrees (0~360)

    Returns:
        CrosswalkPoiResult with before and after POI lists.
    """
    after_lat, after_lon = _offset_point(lat, lon, travel_bearing, CROSSWALK_AFTER_OFFSET_M)

    before_pois, after_pois = await asyncio.gather(
        search_pois_for_dp(lat, lon, travel_bearing),
        search_pois_for_dp(after_lat, after_lon, travel_bearing),
    )

    return CrosswalkPoiResult(before=before_pois, after=after_pois)
