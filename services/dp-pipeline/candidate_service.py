"""Collection and deduplication of Kakao and OSM landmark candidates."""

from __future__ import annotations

import asyncio
import math

from geo import haversine
from osm_service import search_osm_for_dp
from poi_service import (
    CROSSWALK_AFTER_OFFSET_M,
    CrosswalkPoiResult,
    PoiResult,
    search_pois_for_dp,
)

DUPLICATE_DISTANCE_M = 12.0

_OSM_KAKAO_EQUIVALENTS: dict[str, set[str]] = {
    "OSM_PARK": {"AT4"},
    "OSM_SQUARE": {"AT4", "CT1"},
    "OSM_SUBWAY_ENTRANCE": {"SW8"},
    "OSM_BRIDGE": set(),
}


def _normalized_name(name: str) -> str:
    return "".join(char for char in name.casefold() if char.isalnum())


def _compatible_categories(first: PoiResult, second: PoiResult) -> bool:
    if first.category_group_code == second.category_group_code:
        return True
    osm = first if first.source == "OSM" else second if second.source == "OSM" else None
    other = second if osm is first else first
    return bool(osm and other.category_group_code in _OSM_KAKAO_EQUIVALENTS.get(
        osm.category_group_code, set(),
    ))


def _is_duplicate(first: PoiResult, second: PoiResult) -> bool:
    distance = haversine(
        first.latitude, first.longitude, second.latitude, second.longitude,
    )
    if distance > DUPLICATE_DISTANCE_M:
        return False
    same_name = _normalized_name(first.place_name) == _normalized_name(second.place_name)
    return same_name and _compatible_categories(first, second)


def merge_candidates(
    kakao_pois: list[PoiResult],
    osm_pois: list[PoiResult],
) -> list[PoiResult]:
    """Merge candidates, retaining Kakao when a cross-source duplicate exists."""
    merged = list(kakao_pois)
    for osm_poi in osm_pois:
        if any(_is_duplicate(existing, osm_poi) for existing in merged):
            continue
        merged.append(osm_poi)
    merged.sort(key=lambda poi: poi.distance)
    return merged


async def search_candidates_for_dp(
    lat: float,
    lon: float,
    travel_bearing: float,
) -> list[PoiResult]:
    """Collect Kakao POIs and OSM spatial elements concurrently."""
    kakao_pois, osm_pois = await asyncio.gather(
        search_pois_for_dp(lat, lon, travel_bearing),
        search_osm_for_dp(lat, lon, travel_bearing),
    )
    return merge_candidates(kakao_pois, osm_pois)


def _offset_point(
    lat: float,
    lon: float,
    bearing_deg: float,
    distance_m: float,
) -> tuple[float, float]:
    radians = math.radians(bearing_deg)
    north_m = math.cos(radians) * distance_m
    east_m = math.sin(radians) * distance_m
    new_lat = lat + north_m / 111_111.0
    cos_lat = math.cos(math.radians(lat))
    new_lon = lon + east_m / (111_111.0 * cos_lat) if abs(cos_lat) > 1e-9 else lon
    return new_lat, new_lon


async def search_candidates_for_crosswalk(
    lat: float,
    lon: float,
    travel_bearing: float,
) -> CrosswalkPoiResult:
    """Collect merged candidates before and after a crosswalk."""
    after_lat, after_lon = _offset_point(
        lat, lon, travel_bearing, CROSSWALK_AFTER_OFFSET_M,
    )
    before, after = await asyncio.gather(
        search_candidates_for_dp(lat, lon, travel_bearing),
        search_candidates_for_dp(after_lat, after_lon, travel_bearing),
    )
    return CrosswalkPoiResult(before=before, after=after)
