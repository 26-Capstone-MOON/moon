"""Rerouting Service — re-request route and re-run pipeline on deviation.

When DeviationDetector confirms DEVIATED (should_reroute=True), this service
re-requests a route from Tmap and re-runs STEP 1~4 on the new route.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from geo import haversine
from schemas import (
    DecisionPoint,
    Location,
    RerouteRequest,
    RerouteResponse,
    RouteResponse,
)

logger = logging.getLogger(__name__)

# Cache reuse threshold: reuse previous DP data if within this distance
_CACHE_REUSE_DISTANCE_M = 30.0


async def reroute(
    request: RerouteRequest,
    previous_dps: list[DecisionPoint] | None = None,
) -> RerouteResponse:
    """Re-request route from current GPS to destination and re-run pipeline.

    Args:
        request: Reroute request with current GPS and destination.
        previous_dps: DPs from previous route for cache reuse.

    Returns:
        RerouteResponse with new route data or error info.
    """
    # [1] Tmap API re-request
    try:
        tmap_result = await _call_tmap(
            request.current_lat,
            request.current_lng,
            request.dest_lat,
            request.dest_lng,
            request.dest_name,
        )
    except Exception as exc:
        logger.error("Tmap API failed during reroute: %s", exc)
        return RerouteResponse(
            success=False,
            error_message=f"Tmap API 오류: {exc}",
        )

    if not tmap_result or not tmap_result.coordinates:
        return RerouteResponse(
            success=False,
            error_message="경로를 찾을 수 없습니다",
        )

    # [2] Pipeline re-run: STEP 1~4
    try:
        decision_points = _extract_dps(tmap_result)
        decision_points = await _insert_midpoints(
            decision_points, tmap_result.coordinates,
        )
        decision_points = _generate_panorama(decision_points)
    except Exception as exc:
        logger.error("Pipeline step failed during reroute: %s", exc)
        return RerouteResponse(
            success=False,
            error_message=f"파이프라인 오류: {exc}",
        )

    # [3] Cache reuse — match new DPs with previous DPs
    reused_dp_ids: set[str] = set()
    reused_dp_count = 0
    if previous_dps:
        reused_dp_count = _apply_cache_reuse(
            decision_points, previous_dps, reused_dp_ids,
        )

    # [3.5] STEP 6: Generate Korean guidance (replace Tmap placeholders)
    # Skip DPs that already have reused guidance from previous route
    _generate_guidance_for_dps(decision_points, request.dest_name, reused_dp_ids)

    # [4] Build RouteResponse
    route_id = f"route-{uuid.uuid4().hex[:10]}"
    origin = Location(
        latitude=request.current_lat,
        longitude=request.current_lng,
    )
    destination = Location(
        latitude=request.dest_lat,
        longitude=request.dest_lng,
    )

    route_response = RouteResponse(
        route_id=route_id,
        origin=origin,
        destination=destination,
        dest_name=request.dest_name,
        total_distance=tmap_result.total_distance,
        total_time=tmap_result.total_time,
        decision_points=decision_points,
        route_line_string=[
            Location(latitude=lat, longitude=lon)
            for lat, lon in tmap_result.coordinates
        ],
        is_rerouted=True,
        previous_route_id=request.previous_route_id,
    )

    return RerouteResponse(
        success=True,
        route_response=route_response,
        reused_dp_count=reused_dp_count,
    )


# ---------------------------------------------------------------------------
# Pipeline step wrappers (isolate external dependencies for testability)
# ---------------------------------------------------------------------------

async def _call_tmap(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    dest_name: str,
):
    """Call Tmap pedestrian route API. Wraps tmap_service for mockability."""
    from tmap_service import request_pedestrian_route

    return await request_pedestrian_route(
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        dest_lat=dest_lat,
        dest_lng=dest_lng,
        dest_name=dest_name,
    )


def _extract_dps(tmap_result) -> list[DecisionPoint]:
    """Extract DPs from Tmap result. Wraps dp_extractor."""
    from dp_extractor import extract_decision_points

    return extract_decision_points(tmap_result)


async def _insert_midpoints(
    dps: list[DecisionPoint],
    coordinates: list[tuple[float, float]],
) -> list[DecisionPoint]:
    """Insert virtual DPs on long segments. Wraps midpoint_service."""
    from midpoint_service import insert_midpoints

    return await insert_midpoints(dps, coordinates)


def _generate_panorama(dps: list[DecisionPoint]) -> list[DecisionPoint]:
    """Generate panorama request data. Wraps panorama_service."""
    from panorama_service import generate_panorama_requests

    return generate_panorama_requests(dps)


# ---------------------------------------------------------------------------
# STEP 6: Guidance generation for rerouted DPs
# ---------------------------------------------------------------------------


def _generate_guidance_for_dps(
    decision_points: list[DecisionPoint],
    dest_name: str = "",
    skip_dp_ids: set[str] | None = None,
) -> None:
    """Replace Tmap placeholder guidance with proper Korean guidance.

    Uses guidance_generator for non-VIRTUAL DPs. VIRTUAL DPs already have
    guidance from midpoint_service. Cache-reused DPs (in skip_dp_ids) are
    skipped. Operates in-place.
    """
    from constants import TURN_TYPE_TO_ACTION
    from guidance_generator import generate_guidance

    _skip = skip_dp_ids or set()
    prev_landmark_name: str | None = None
    for i, dp in enumerate(decision_points):
        if dp.dp_type == "VIRTUAL":
            if dp.selected_landmark is not None:
                prev_landmark_name = dp.selected_landmark.name
            else:
                prev_landmark_name = None
            continue

        if dp.dp_id in _skip:
            # Cache-reused DP already has good guidance; track landmark for chain
            if dp.selected_landmark is not None:
                prev_landmark_name = dp.selected_landmark.name
            else:
                prev_landmark_name = None
            continue

        next_dp_distance: float | None = None
        if i < len(decision_points) - 1:
            next_dp_distance = (
                decision_points[i + 1].distance_from_start
                - dp.distance_from_start
            )

        next_action: str | None = None
        if dp.dp_type == "DEPARTURE" and i < len(decision_points) - 1:
            next_tt = decision_points[i + 1].turn_type
            if next_tt is not None:
                next_action = TURN_TYPE_TO_ACTION.get(next_tt)

        dp.guidance = generate_guidance(
            dp_type=dp.dp_type,
            turn_type=dp.turn_type,
            selected_landmark=None,
            match_status=None,
            environment_desc=None,
            facility_visible=None,
            prev_landmark_name=prev_landmark_name,
            next_dp_distance=next_dp_distance,
            dest_name=dest_name,
            distance_from_start=dp.distance_from_start,
            next_action=next_action,
            tmap_description=dp.tmap_description,
        )

        prev_landmark_name = None


# ---------------------------------------------------------------------------
# Cache reuse
# ---------------------------------------------------------------------------

def _apply_cache_reuse(
    new_dps: list[DecisionPoint],
    previous_dps: list[DecisionPoint],
    reused_ids: set[str] | None = None,
) -> int:
    """Reuse POI, panorama, and guidance from previous DPs within 30m with same type.

    Args:
        new_dps: Decision points from the new route (mutated in place).
        previous_dps: Decision points from the previous route.
        reused_ids: If provided, dp_ids of reused DPs are added to this set.

    Returns:
        Number of DPs where cache data was reused.
    """
    reused = 0
    for new_dp in new_dps:
        for prev_dp in previous_dps:
            if new_dp.dp_type != prev_dp.dp_type:
                continue
            dist = haversine(
                new_dp.location.latitude,
                new_dp.location.longitude,
                prev_dp.location.latitude,
                prev_dp.location.longitude,
            )
            if dist <= _CACHE_REUSE_DISTANCE_M:
                if prev_dp.selected_landmark is not None:
                    new_dp.selected_landmark = prev_dp.selected_landmark
                if prev_dp.panorama_request is not None:
                    new_dp.panorama_request = prev_dp.panorama_request
                # Reuse guidance from previous route (already generated)
                new_dp.guidance = prev_dp.guidance
                if reused_ids is not None:
                    reused_ids.add(new_dp.dp_id)
                reused += 1
                break
    return reused
