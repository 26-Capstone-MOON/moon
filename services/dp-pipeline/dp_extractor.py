"""STEP 1: Extract Decision Points from Tmap route data by turnType filtering."""

from __future__ import annotations

import uuid
from typing import Optional

from constants import (
    EXCLUDED_TURN_TYPES,
    TURN_TYPE_TO_ACTION,
    TURN_TYPE_TO_DP_TYPE,
)
from geo import calculate_bearing, haversine
from schemas import DecisionPoint, Guidance, Location
from tmap_service import TmapPoint, TmapRouteResult


def _generate_dp_id() -> str:
    return f"dp-{uuid.uuid4().hex[:8]}"


def _calculate_distance_from_start(
    point_index: int,
    coordinates: list[tuple[float, float]],
) -> float:
    """Sum haversine distances along the route from start to point_index."""
    if point_index <= 0 or not coordinates:
        return 0.0
    total = 0.0
    end = min(point_index, len(coordinates) - 1)
    for i in range(end):
        total += haversine(
            coordinates[i][0], coordinates[i][1],
            coordinates[i + 1][0], coordinates[i + 1][1],
        )
    return total


def _calculate_bearing_at_dp(
    point_index: int,
    coordinates: list[tuple[float, float]],
) -> float:
    """Calculate travel bearing at a DP using route coordinates.

    Uses the segment starting at point_index. Falls back to previous segment
    if point_index is at or beyond the last coordinate.
    """
    if len(coordinates) < 2:
        return 0.0

    idx = min(point_index, len(coordinates) - 1)

    # Use forward segment if available
    if idx < len(coordinates) - 1:
        return calculate_bearing(
            coordinates[idx][0], coordinates[idx][1],
            coordinates[idx + 1][0], coordinates[idx + 1][1],
        )

    # At the last coordinate, use the previous segment
    return calculate_bearing(
        coordinates[idx - 1][0], coordinates[idx - 1][1],
        coordinates[idx][0], coordinates[idx][1],
    )


def _make_placeholder_guidance(turn_type: int, description: str) -> Guidance:
    """Create placeholder guidance from Tmap description.

    Real guidance is generated later in STEP 6 (guidance_generator.py)
    after POI collection and scoring. This placeholder preserves the
    Tmap description and action type for intermediate processing.
    """
    action = TURN_TYPE_TO_ACTION.get(turn_type)
    return Guidance(
        primary=description or "안내 없음",
        pre_alert=None,
        action=action,
    )


def extract_decision_points(
    tmap_result: TmapRouteResult,
) -> list[DecisionPoint]:
    """Extract Decision Points from Tmap response by filtering turnType.

    Filters Tmap Point features by TURN_TYPE_TO_DP_TYPE mapping,
    excludes turnTypes in EXCLUDED_TURN_TYPES, and builds DecisionPoint
    models with location, bearing, and placeholder guidance.

    Args:
        tmap_result: Parsed Tmap API response

    Returns:
        Ordered list of DecisionPoints along the route
    """
    decision_points: list[DecisionPoint] = []

    for point in tmap_result.points:
        dp_type = TURN_TYPE_TO_DP_TYPE.get(point.turn_type)

        if dp_type is None:
            if point.turn_type not in EXCLUDED_TURN_TYPES:
                # Unknown turnType — skip silently
                pass
            continue

        distance_from_start = _calculate_distance_from_start(
            point.point_index, tmap_result.coordinates,
        )
        bearing = _calculate_bearing_at_dp(
            point.point_index, tmap_result.coordinates,
        )

        dp = DecisionPoint(
            dp_id=_generate_dp_id(),
            dp_type=dp_type,
            turn_type=point.turn_type,
            location=Location(latitude=point.latitude, longitude=point.longitude),
            bearing=bearing,
            distance_from_start=distance_from_start,
            guidance=_make_placeholder_guidance(point.turn_type, point.description),
            selected_landmark=None,
            panorama_request=None,
        )
        decision_points.append(dp)

    # Sort by distance from start (should already be ordered, but ensure)
    decision_points.sort(key=lambda dp: dp.distance_from_start)

    return decision_points
