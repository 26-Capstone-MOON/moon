"""Tmap pedestrian route API integration and GeoJSON response parsing."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from fastapi import HTTPException

from config import settings

TMAP_PEDESTRIAN_URL = "https://apis.openapi.sk.com/tmap/routes/pedestrian?version=1"
TMAP_TIMEOUT = 10.0


@dataclass
class TmapPoint:
    """A Point feature extracted from Tmap GeoJSON (guidance point)."""

    latitude: float
    longitude: float
    turn_type: int
    description: str
    point_index: int  # index into the LineString coordinate array


@dataclass
class TmapRouteResult:
    """Parsed result from Tmap pedestrian route API."""

    coordinates: list[tuple[float, float]]  # (lat, lon) full route polyline
    points: list[TmapPoint]  # guidance Point features
    total_distance: float  # meters
    total_time: float  # seconds


def _parse_geojson(feature_collection: dict) -> TmapRouteResult:
    """Parse Tmap GeoJSON FeatureCollection into structured data.

    Tmap returns Features with geometry type Point (guidance) or LineString (path segments).
    Point features have turnType, description, pointIndex in properties.
    LineString features have distance, time in properties.
    """
    coordinates: list[tuple[float, float]] = []
    points: list[TmapPoint] = []
    total_distance: float = 0.0
    total_time: float = 0.0
    coord_set: set[tuple[float, float]] = set()

    features = feature_collection.get("features", [])
    if not features:
        raise HTTPException(status_code=502, detail="Tmap returned empty features")

    for feature in features:
        geometry = feature.get("geometry", {})
        properties = feature.get("properties", {})
        geom_type = geometry.get("type", "")

        if geom_type == "Point":
            coords = geometry.get("coordinates", [])
            if len(coords) < 2:
                continue
            lon, lat = float(coords[0]), float(coords[1])
            turn_type = int(properties.get("turnType", 0))
            description = properties.get("description", "")
            point_index = int(properties.get("pointIndex", 0))

            points.append(TmapPoint(
                latitude=lat,
                longitude=lon,
                turn_type=turn_type,
                description=description,
                point_index=point_index,
            ))

        elif geom_type == "LineString":
            raw_coords = geometry.get("coordinates", [])
            for coord in raw_coords:
                if len(coord) < 2:
                    continue
                lon, lat = float(coord[0]), float(coord[1])
                key = (lat, lon)
                if key not in coord_set:
                    coord_set.add(key)
                    coordinates.append(key)

            total_distance += float(properties.get("distance", 0))
            total_time += float(properties.get("time", 0))

    if not coordinates:
        raise HTTPException(status_code=502, detail="Tmap returned no route coordinates")

    return TmapRouteResult(
        coordinates=coordinates,
        points=points,
        total_distance=total_distance,
        total_time=total_time,
    )


async def request_pedestrian_route(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    dest_name: str = "목적지",
) -> TmapRouteResult:
    """Call Tmap pedestrian route API and return parsed result.

    Args:
        origin_lat: Origin latitude (WGS84)
        origin_lng: Origin longitude (WGS84)
        dest_lat: Destination latitude (WGS84)
        dest_lng: Destination longitude (WGS84)
        dest_name: Destination name for Tmap display

    Returns:
        TmapRouteResult with coordinates, guidance points, distance, time

    Raises:
        HTTPException: On API key error, timeout, or invalid response
    """
    if not settings.tmap_api_key:
        raise HTTPException(status_code=500, detail="TMAP_API_KEY not configured")

    headers = {
        "appKey": settings.tmap_api_key,
        "Content-Type": "application/json",
    }

    body = {
        "startX": str(origin_lng),
        "startY": str(origin_lat),
        "endX": str(dest_lng),
        "endY": str(dest_lat),
        "startName": "출발지",
        "endName": dest_name,
        "reqCoordType": "WGS84GEO",
        "resCoordType": "WGS84GEO",
    }

    async with httpx.AsyncClient(timeout=TMAP_TIMEOUT) as client:
        try:
            response = await client.post(TMAP_PEDESTRIAN_URL, headers=headers, json=body)
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Tmap API request timed out")
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Tmap API request failed: {e}")

    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="Tmap API key is invalid")
    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Tmap API returned status {response.status_code}",
        )

    try:
        data = response.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="Tmap returned invalid JSON")

    return _parse_geojson(data)
