"""Google Places API integration — batch isOpen lookup for POIs.

Checks business hour status for POI candidates to compute P(h) correction.
"""

from __future__ import annotations

import asyncio

import httpx

from config import settings
from poi_service import PoiResult

PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
PLACES_DETAIL_URL = "https://maps.googleapis.com/maps/api/place/details/json"
PLACES_TIMEOUT = 5.0
MAX_CONCURRENT = 5  # limit parallel Google API calls


def poi_identity_key(poi: PoiResult) -> str:
    """Build a stable key for a POI instance across scoring and isOpen lookup."""
    return (
        f"{poi.place_name}|{poi.category_group_code}|"
        f"{poi.latitude:.6f}|{poi.longitude:.6f}"
    )


async def _find_place_id(
    client: httpx.AsyncClient,
    poi: PoiResult,
) -> str | None:
    """Find Google place_id for a POI using Nearby Search.

    Args:
        client: Shared httpx async client
        poi: POI with coordinates and name

    Returns:
        Google place_id string, or None if not found.
    """
    params = {
        "location": f"{poi.latitude},{poi.longitude}",
        "radius": "50",
        "keyword": poi.place_name,
        "key": settings.google_places_api_key,
    }
    try:
        resp = await client.get(PLACES_NEARBY_URL, params=params)
    except (httpx.TimeoutException, httpx.RequestError):
        return None

    if resp.status_code != 200:
        return None

    data = resp.json()
    results = data.get("results", [])
    if not results:
        return None

    return results[0].get("place_id")


async def _check_is_open(
    client: httpx.AsyncClient,
    place_id: str,
) -> str:
    """Check if a place is currently open via Place Details API.

    Args:
        client: Shared httpx async client
        place_id: Google place_id

    Returns:
        "OPEN", "CLOSED", or "UNKNOWN".
    """
    params = {
        "place_id": place_id,
        "fields": "opening_hours",
        "key": settings.google_places_api_key,
    }
    try:
        resp = await client.get(PLACES_DETAIL_URL, params=params)
    except (httpx.TimeoutException, httpx.RequestError):
        return "UNKNOWN"

    if resp.status_code != 200:
        return "UNKNOWN"

    data = resp.json()
    result = data.get("result", {})
    opening_hours = result.get("opening_hours")

    if opening_hours is None:
        return "UNKNOWN"

    is_open = opening_hours.get("open_now")
    if is_open is None:
        return "UNKNOWN"

    return "OPEN" if is_open else "CLOSED"


async def _lookup_single_poi(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    poi: PoiResult,
) -> tuple[str, str]:
    """Lookup isOpen status for a single POI with concurrency limit.

    Args:
        client: Shared httpx async client
        semaphore: Concurrency limiter
        poi: POI to check

    Returns:
        (place_name, is_open_status) tuple.
    """
    async with semaphore:
        place_id = await _find_place_id(client, poi)
        if not place_id:
            return poi.place_name, "UNKNOWN"

        status = await _check_is_open(client, place_id)
        return poi.place_name, status


async def fetch_is_open_statuses(
    pois: list[PoiResult],
) -> dict[str, str]:
    """Batch lookup isOpen status for multiple POIs.

    Args:
        pois: List of POIs to check

    Returns:
        Dict mapping stable POI key → "OPEN"|"CLOSED"|"UNKNOWN".
        Returns all "UNKNOWN" if API key is missing.
    """
    if not settings.google_places_api_key or not pois:
        return {poi_identity_key(poi): "UNKNOWN" for poi in pois}

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async with httpx.AsyncClient(timeout=PLACES_TIMEOUT) as client:
        tasks = [
            _lookup_single_poi(client, semaphore, poi)
            for poi in pois
        ]
        results = await asyncio.gather(*tasks)

    status_map: dict[str, str] = {}
    for poi, (_, status) in zip(pois, results):
        status_map[poi_identity_key(poi)] = status
    return status_map
