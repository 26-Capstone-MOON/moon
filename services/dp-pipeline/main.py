"""Local FastAPI app for mock and live dp-pipeline verification."""

from __future__ import annotations

import hashlib
import math
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from constants import (
    ARRIVAL_DISTANCE,
    LEFT_PRIMARY_TURN_TYPES,
    PRE_ALERT_DISTANCE,
    RIGHT_PRIMARY_TURN_TYPES,
    VIRTUAL_DP_THRESHOLD,
)
from dp_extractor import extract_decision_points
from geo import (
    calculate_bearing,
    haversine,
    interpolate_linestring,
    interpolate_linestring_with_distance,
    point_to_linestring_distance,
    project_distance_on_linestring,
)
from midpoint_service import insert_midpoints
from places_service import fetch_is_open_statuses, poi_identity_key
from poi_service import PoiResult, search_pois_for_crosswalk, search_pois_for_dp
from deviation_detector import DeviationDetector
from conversation_service import chat as conversation_chat
from rerouting_service import reroute as reroute_service
from schemas import (
    ConversationRequest,
    ConversationResponse,
    RerouteRequest,
    ApiResponse,
    DecisionPoint,
    DeviationResult,
    DeviationResponse,
    GpsReading,
    Guidance,
    Location,
    PanoramaDirection,
    PanoramaRequest,
    Progress,
    RouteRequest,
    RouteResponse,
    SelectedLandmark,
)
from guidance_generator import generate_guidance
from tts_service import synthesize, synthesize_guidance
from scoring_service import ScoredPoi, rank_pois, select_landmark
from sequence_optimizer import optimize_sequence
from smoke_navigation_check import build_report
from tmap_service import request_pedestrian_route

WALKING_SPEED_MPS = 1.2

# ---------------------------------------------------------------------------
# In-memory route cache
# ---------------------------------------------------------------------------
_route_cache: dict[str, RouteResponse] = {}

# ---------------------------------------------------------------------------
# In-memory DeviationDetector session cache
# ---------------------------------------------------------------------------
_detector_cache: dict[str, DeviationDetector] = {}

# ---------------------------------------------------------------------------
# Per-route completed DP tracking (dp_id set)
# ---------------------------------------------------------------------------
_completed_dps: dict[str, set[str]] = {}

DEVIATION_DISTANCE_THRESHOLD = 20.0

TURN_LEFT = 12
TURN_RIGHT = 13

VIRTUAL_LANDMARKS: list[tuple[str, str, str]] = [
    ("국민은행", "BK9", "LEFT"),
    ("스타벅스", "CE7", "RIGHT"),
    ("GS25", "CS2", "LEFT"),
]


class MockDeviationRequest(BaseModel):
    route_id: str
    current_location: Location
    route_line_string: list[Location]
    current_dp_id: str
    current_dp_location: Location
    completed_dps: list[str] = []


app = FastAPI(
    title="MOON dp-pipeline verification server",
    version="0.1.0",
    description=(
        "Local verification endpoints for Postman. "
        "Mock endpoints stay local, and /api/smoke/tmap performs a live Tmap call."
    ),
)


async def _attach_tts_audio(route_response: RouteResponse) -> RouteResponse:
    """Generate Google Cloud TTS audio for all DP guidance texts."""
    for dp in route_response.decision_points:
        if dp.guidance:
            primary_audio, pre_alert_audio = await synthesize_guidance(
                dp.guidance.primary,
                dp.guidance.pre_alert,
            )
            dp.guidance.primary_audio = primary_audio
            dp.guidance.pre_alert_audio = pre_alert_audio
    return route_response


def _location_tuple(location: Location) -> tuple[float, float]:
    return location.latitude, location.longitude


def _location_from_tuple(coords: tuple[float, float]) -> Location:
    return Location(latitude=coords[0], longitude=coords[1])


def _meters_to_latitude(delta_m: float) -> float:
    return delta_m / 111_111.0


def _meters_to_longitude(delta_m: float, latitude: float) -> float:
    cos_lat = math.cos(math.radians(latitude))
    if abs(cos_lat) < 1e-9:
        return 0.0
    return delta_m / (111_111.0 * cos_lat)


def _offset_point(lat: float, lon: float, bearing_deg: float, distance_m: float) -> tuple[float, float]:
    radians = math.radians(bearing_deg)
    north_m = math.cos(radians) * distance_m
    east_m = math.sin(radians) * distance_m
    return (
        lat + _meters_to_latitude(north_m),
        lon + _meters_to_longitude(east_m, lat),
    )


def _route_distance(coords: list[tuple[float, float]]) -> float:
    total = 0.0
    for index in range(len(coords) - 1):
        start = coords[index]
        end = coords[index + 1]
        total += haversine(start[0], start[1], end[0], end[1])
    return total


def _build_route_coords(origin: Location, destination: Location) -> list[tuple[float, float]]:
    start = _location_tuple(origin)
    end = _location_tuple(destination)
    direct_distance = haversine(start[0], start[1], end[0], end[1])

    if direct_distance < 120:
        return [start, end]

    mid_lat = (start[0] + end[0]) / 2
    mid_lon = (start[1] + end[1]) / 2
    bearing = calculate_bearing(start[0], start[1], end[0], end[1])
    bend_side = 90.0 if destination.longitude >= origin.longitude else -90.0
    bend_offset_m = min(40.0, max(20.0, direct_distance * 0.08))
    bend = _offset_point(mid_lat, mid_lon, (bearing + bend_side) % 360, bend_offset_m)
    return [start, bend, end]


def _turn_type_for_bend(coords: list[tuple[float, float]]) -> int | None:
    if len(coords) < 3:
        return None

    first = calculate_bearing(coords[0][0], coords[0][1], coords[1][0], coords[1][1])
    second = calculate_bearing(coords[1][0], coords[1][1], coords[2][0], coords[2][1])
    delta = ((second - first + 540) % 360) - 180

    if delta <= -20:
        return TURN_LEFT
    if delta >= 20:
        return TURN_RIGHT
    return None


def _make_panorama_request(location: Location, primary_label: str = "FRONT") -> PanoramaRequest:
    directions = [
        PanoramaDirection(pan=0.0, label="FRONT", is_primary=primary_label == "FRONT"),
        PanoramaDirection(pan=-90.0, label="LEFT", is_primary=primary_label == "LEFT"),
        PanoramaDirection(pan=90.0, label="RIGHT", is_primary=primary_label == "RIGHT"),
    ]
    return PanoramaRequest(location=location, directions=directions)


def _make_virtual_landmark(index: int) -> SelectedLandmark:
    name, category_code, position = VIRTUAL_LANDMARKS[index % len(VIRTUAL_LANDMARKS)]
    return SelectedLandmark(
        name=name,
        category_code=category_code,
        position=position,
        distance=18.0 + index * 4,
        score=1.3 - (index * 0.05),
        match_status="POI_ONLY",
        is_open=True,
    )


def _make_turn_landmark(turn_type: int) -> SelectedLandmark:
    is_right_turn = turn_type == TURN_RIGHT
    return SelectedLandmark(
        name="올리브영" if is_right_turn else "GS25",
        category_code="CS2" if not is_right_turn else "CE7",
        position="RIGHT" if is_right_turn else "LEFT",
        distance=14.0,
        score=1.72,
        match_status="POI_ONLY",
        is_open=True,
    )


def _direction_text(turn_type: int) -> str:
    return "right" if turn_type == TURN_RIGHT else "left"


def _action_text(turn_type: int) -> str:
    return "RIGHT_TURN" if turn_type == TURN_RIGHT else "LEFT_TURN"


def _mock_route_id(request: RouteRequest) -> str:
    key = (
        f"{request.origin_lat:.6f}:{request.origin_lng:.6f}:"
        f"{request.dest_lat:.6f}:{request.dest_lng:.6f}:{request.dest_name}"
    )
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
    return f"mock-route-{digest}"


def _build_mock_route_response(request: RouteRequest) -> RouteResponse:
    origin = Location(latitude=request.origin_lat, longitude=request.origin_lng)
    destination = Location(latitude=request.dest_lat, longitude=request.dest_lng)
    route_coords = _build_route_coords(origin, destination)
    total_distance = _route_distance(route_coords)
    route_id = _mock_route_id(request)
    destination_name = request.dest_name or "destination"

    decision_points: list[DecisionPoint] = [
        DecisionPoint(
            dp_id="dp-start",
            dp_type="DEPARTURE",
            turn_type=200,
            location=origin,
            distance_from_start=0.0,
            guidance=Guidance(
                primary=f"Start walking toward {destination_name}.",
                pre_alert=None,
                action=None,
            ),
            selected_landmark=None,
            panorama_request=_make_panorama_request(origin, primary_label="FRONT"),
        )
    ]

    turn_type = _turn_type_for_bend(route_coords)
    if turn_type is not None:
        bend_location = _location_from_tuple(route_coords[1])
        landmark = _make_turn_landmark(turn_type)
        direction = _direction_text(turn_type)
        decision_points.append(
            DecisionPoint(
                dp_id="dp-turn-1",
                dp_type="DIRECTION_CHANGE",
                turn_type=turn_type,
                location=bend_location,
                distance_from_start=haversine(
                    route_coords[0][0],
                    route_coords[0][1],
                    route_coords[1][0],
                    route_coords[1][1],
                ),
                guidance=Guidance(
                    primary=f"Turn {direction} at {landmark.name}.",
                    pre_alert=f"Soon you will see {landmark.name}. Get ready to turn {direction}.",
                    action=_action_text(turn_type),
                ),
                selected_landmark=landmark,
                panorama_request=_make_panorama_request(
                    bend_location,
                    primary_label=landmark.position,
                ),
            )
        )

    if total_distance > VIRTUAL_DP_THRESHOLD:
        spaced_points = interpolate_linestring_with_distance(route_coords, VIRTUAL_DP_THRESHOLD)
        for index, (distance_from_start, coords) in enumerate(spaced_points, start=1):
            if total_distance - distance_from_start < ARRIVAL_DISTANCE * 2:
                continue
            landmark = _make_virtual_landmark(index - 1)
            location = _location_from_tuple(coords)
            direction = landmark.position.lower()
            decision_points.append(
                DecisionPoint(
                    dp_id=f"dp-virtual-{index}",
                    dp_type="VIRTUAL",
                    turn_type=None,
                    location=location,
                    distance_from_start=distance_from_start,
                    guidance=Guidance(
                        primary=f"If {landmark.name} is on your {direction}, keep going straight.",
                        pre_alert=None,
                        action=None,
                    ),
                    selected_landmark=landmark,
                    panorama_request=PanoramaRequest(
                        location=location,
                        directions=[
                            PanoramaDirection(
                                pan=0.0,
                                label="FRONT",
                                is_primary=True,
                            )
                        ],
                    ),
                )
            )

    decision_points.append(
        DecisionPoint(
            dp_id="dp-arrival",
            dp_type="ARRIVAL",
            turn_type=201,
            location=destination,
            distance_from_start=total_distance,
            guidance=Guidance(
                primary=f"You have arrived at {destination_name}.",
                pre_alert=f"{destination_name} is just ahead.",
                action=None,
            ),
            selected_landmark=None,
            panorama_request=_make_panorama_request(destination, primary_label="FRONT"),
        )
    )

    decision_points.sort(key=lambda decision_point: decision_point.distance_from_start)

    return RouteResponse(
        route_id=route_id,
        origin=origin,
        destination=destination,
        dest_name=request.dest_name,
        total_distance=total_distance,
        total_time=total_distance / WALKING_SPEED_MPS,
        decision_points=decision_points,
        route_line_string=[_location_from_tuple(coords) for coords in route_coords],
        is_rerouted=False,
        previous_route_id=None,
    )


def _classify_trigger(distance_to_dp_m: float) -> str | None:
    if distance_to_dp_m <= ARRIVAL_DISTANCE:
        return "ARRIVAL"
    if distance_to_dp_m <= PRE_ALERT_DISTANCE:
        return "PRE_ALERT"
    return None


def _build_mock_deviation_response(request: MockDeviationRequest) -> DeviationResponse:
    route_coords = [_location_tuple(location) for location in request.route_line_string]
    current = _location_tuple(request.current_location)
    current_dp = _location_tuple(request.current_dp_location)
    destination = route_coords[-1]

    distance_to_route = point_to_linestring_distance(current[0], current[1], route_coords)
    distance_to_dp = haversine(current[0], current[1], current_dp[0], current_dp[1])
    distance_to_destination = haversine(current[0], current[1], destination[0], destination[1])

    trigger = _classify_trigger(distance_to_dp)
    if distance_to_destination <= ARRIVAL_DISTANCE:
        navigation_state = "ARRIVED"
        trigger = "ARRIVAL"
        guidance = Guidance(
            primary="You have reached the destination.",
            pre_alert=None,
            action=None,
        )
    elif distance_to_route > DEVIATION_DISTANCE_THRESHOLD:
        navigation_state = "DEVIATION_SUSPECTED"
        guidance = Guidance(
            primary="You seem to be leaving the planned route.",
            pre_alert=None,
            action=None,
        )
    else:
        navigation_state = "ON_ROUTE"
        if trigger == "ARRIVAL":
            guidance = Guidance(
                primary=f"Arrived at {request.current_dp_id}.",
                pre_alert=None,
                action=None,
            )
        elif trigger == "PRE_ALERT":
            guidance = Guidance(
                primary=f"{request.current_dp_id} is ahead.",
                pre_alert=f"Decision point {request.current_dp_id} is within {PRE_ALERT_DISTANCE:.0f} meters.",
                action=None,
            )
        else:
            guidance = Guidance(
                primary="Continue along the current route.",
                pre_alert=None,
                action=None,
            )

    remaining_distance = max(distance_to_destination, 0.0)
    progress = Progress(
        completed_dps=request.completed_dps,
        current_dp_id=request.current_dp_id,
        remaining_dps=[request.current_dp_id],
        distance_remaining=remaining_distance,
        time_remaining=remaining_distance / WALKING_SPEED_MPS,
    )

    return DeviationResponse(
        navigation_state=navigation_state,
        current_dp_id=request.current_dp_id,
        distance_to_dp=distance_to_dp,
        trigger=trigger,
        guidance=guidance,
        progress=progress,
    )


def _build_live_tmap_request_summary(request: RouteRequest) -> dict:
    return {
        "origin": {
            "latitude": round(request.origin_lat, 6),
            "longitude": round(request.origin_lng, 6),
        },
        "destination": {
            "latitude": round(request.dest_lat, 6),
            "longitude": round(request.dest_lng, 6),
        },
        "dest_name": request.dest_name,
    }


def _summarize_live_decision_point(decision_point: DecisionPoint) -> dict:
    summary: dict = {
        "dp_id": decision_point.dp_id,
        "dp_type": decision_point.dp_type,
        "turn_type": decision_point.turn_type,
        "bearing": (
            round(decision_point.bearing, 2)
            if decision_point.bearing is not None
            else None
        ),
        "distance_from_start_m": round(decision_point.distance_from_start, 2),
        "location": {
            "latitude": round(decision_point.location.latitude, 6),
            "longitude": round(decision_point.location.longitude, 6),
        },
        "guidance": {
            "primary": decision_point.guidance.primary,
            "pre_alert": decision_point.guidance.pre_alert,
            "action": decision_point.guidance.action,
        },
    }
    if decision_point.selected_landmark is not None:
        lm = decision_point.selected_landmark
        summary["selected_landmark"] = {
            "name": lm.name,
            "category_code": lm.category_code,
            "position": lm.position,
            "distance": round(lm.distance, 1),
            "score": round(lm.score, 4),
            "match_status": lm.match_status,
            "is_open": lm.is_open,
        }
    if decision_point.panorama_request is not None:
        pr = decision_point.panorama_request
        summary["panorama_request"] = {
            "location": {
                "latitude": round(pr.location.latitude, 6),
                "longitude": round(pr.location.longitude, 6),
            },
            "directions": [
                {"pan": d.pan, "label": d.label, "is_primary": d.is_primary}
                for d in pr.directions
            ],
        }
    return summary


def _count_decision_points_by_type(decision_points: list[DecisionPoint]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for decision_point in decision_points:
        counts[decision_point.dp_type] = counts.get(decision_point.dp_type, 0) + 1
    return counts


def _summarize_poi(poi: PoiResult) -> dict:
    return {
        "name": poi.place_name,
        "category": poi.category_group_code,
        "distance_m": round(poi.distance, 1),
        "position": poi.position,
        "p_value": poi.p_value,
    }


async def _build_live_pipeline_summary(
    request: RouteRequest,
    *,
    scenario: str,
) -> dict:
    tmap_result = await request_pedestrian_route(
        origin_lat=request.origin_lat,
        origin_lng=request.origin_lng,
        dest_lat=request.dest_lat,
        dest_lng=request.dest_lng,
        dest_name=request.dest_name or "목적지",
    )

    decision_points_before_midpoint = extract_decision_points(tmap_result)

    decision_points = await insert_midpoints(
        decision_points_before_midpoint,
        tmap_result.coordinates,
    )
    poi_summary: list[dict] = []

    for dp in decision_points:
        bearing = _get_dp_bearing(dp, tmap_result.coordinates)

        if dp.dp_type == "CROSSWALK":
            crosswalk_result = await search_pois_for_crosswalk(
                dp.location.latitude,
                dp.location.longitude,
                bearing,
            )
            poi_summary.append({
                "dp_id": dp.dp_id,
                "dp_type": dp.dp_type,
                "distance_from_start_m": round(dp.distance_from_start, 1),
                "before_crossing": {
                    "poi_count": len(crosswalk_result.before),
                    "top_pois": [
                        _summarize_poi(p)
                        for p in crosswalk_result.before[:3]
                    ],
                },
                "after_crossing": {
                    "poi_count": len(crosswalk_result.after),
                    "top_pois": [
                        _summarize_poi(p)
                        for p in crosswalk_result.after[:3]
                    ],
                },
            })
            continue

        pois = await search_pois_for_dp(
            dp.location.latitude,
            dp.location.longitude,
            bearing,
        )
        poi_summary.append({
            "dp_id": dp.dp_id,
            "dp_type": dp.dp_type,
            "distance_from_start_m": round(dp.distance_from_start, 1),
            "poi_count": len(pois),
            "top_pois": [_summarize_poi(p) for p in pois[:3]],
        })

    return {
        "scenario": scenario,
        "request": _build_live_tmap_request_summary(request),
        "route": {
            "total_distance_m": round(tmap_result.total_distance, 2),
            "total_time_s": round(tmap_result.total_time, 2),
            "coordinate_count": len(tmap_result.coordinates),
            "point_feature_count": len(tmap_result.points),
        },
        "decision_point_summary": {
            "count": len(decision_points),
            "by_type": _count_decision_points_by_type(decision_points),
        },
        "dp_summary": {
            "before_midpoint": len(decision_points_before_midpoint),
            "after_midpoint": len(decision_points),
            "virtual_dps_inserted": (
                len(decision_points) - len(decision_points_before_midpoint)
            ),
            "by_type": _count_decision_points_by_type(decision_points),
        },
        "decision_points": [
            _summarize_live_decision_point(decision_point)
            for decision_point in decision_points
        ],
        "poi_per_dp": poi_summary,
    }


@app.get("/", response_model=ApiResponse)
def root() -> ApiResponse:
    return ApiResponse(
        data={
            "service": "MOON dp-pipeline verification server",
            "available_endpoints": [
                "/health",
                "/api/route",
                "/api/smoke/navigation",
                "/api/smoke/tmap",
                "/api/smoke/midpoint-poi",
                "/api/route/{route_id}",
                "/api/route/mock",
                "/api/deviation",
                "/api/reroute",
                "/api/chat",
                "/api/deviation/mock",
            ],
        }
    )


@app.get("/health", response_model=ApiResponse)
def health() -> ApiResponse:
    return ApiResponse(data={"status": "ok"})


@app.get("/api/smoke/navigation", response_model=ApiResponse)
def navigation_smoke() -> ApiResponse:
    return ApiResponse(data=build_report())


@app.post("/api/smoke/tmap", response_model=ApiResponse)
async def tmap_smoke(request: RouteRequest) -> ApiResponse:
    return ApiResponse(
        data=await _build_live_pipeline_summary(
            request,
            scenario="tmap_live_dp_pipeline",
        )
    )


@app.post("/api/route/mock", response_model=ApiResponse)
async def route_mock(request: RouteRequest) -> ApiResponse:
    route_response = _build_mock_route_response(request)
    route_response = await _attach_tts_audio(route_response)
    return ApiResponse(data=route_response)


@app.post("/api/deviation/mock", response_model=ApiResponse)
def deviation_mock(request: MockDeviationRequest) -> ApiResponse:
    return ApiResponse(data=_build_mock_deviation_response(request))


@app.post("/api/smoke/midpoint-poi", response_model=ApiResponse)
async def midpoint_poi_smoke(request: RouteRequest) -> ApiResponse:
    """Smoke test: Tmap -> DP extraction -> midpoint insertion -> POI collection."""
    return ApiResponse(
        data=await _build_live_pipeline_summary(
            request,
            scenario="midpoint_poi_pipeline",
        ),
    )


# ---------------------------------------------------------------------------
# Live route pipeline: Tmap → DP → midpoint → POI/scoring → RouteResponse
# ---------------------------------------------------------------------------

def _primary_label_for_turn_type(turn_type: int | None) -> str:
    """Determine panorama isPrimary direction from turnType."""
    if turn_type is None:
        return "FRONT"
    if turn_type in LEFT_PRIMARY_TURN_TYPES:
        return "LEFT"
    if turn_type in RIGHT_PRIMARY_TURN_TYPES:
        return "RIGHT"
    return "FRONT"


def _build_3dir_panorama(location: Location, turn_type: int | None) -> PanoramaRequest:
    """Build 3-direction panorama request with turnType-based isPrimary."""
    primary = _primary_label_for_turn_type(turn_type)
    return PanoramaRequest(
        location=location,
        directions=[
            PanoramaDirection(pan=0.0, label="FRONT", is_primary=primary == "FRONT"),
            PanoramaDirection(pan=-90.0, label="LEFT", is_primary=primary == "LEFT"),
            PanoramaDirection(pan=90.0, label="RIGHT", is_primary=primary == "RIGHT"),
        ],
    )


def _resolve_is_open_status(
    poi: PoiResult,
    is_open_map: dict[str, str],
) -> str:
    """Resolve isOpen status using the stable POI identity key."""
    return is_open_map.get(
        poi_identity_key(poi),
        is_open_map.get(poi.place_name, "UNKNOWN"),
    )


def _scored_from_selected_landmark(landmark: SelectedLandmark) -> ScoredPoi:
    """Synthesize a ScoredPoi from an existing SelectedLandmark.

    Used so VIRTUAL DPs (already finalized by midpoint_service) can participate
    in the sequence-optimizer chain for name-dedup. The single-candidate list
    ensures the optimizer cannot swap a VIRTUAL DP's landmark.
    """
    location = landmark.location
    poi = PoiResult(
        place_name=landmark.name,
        category_group_code=landmark.category_code,
        category_name="",
        latitude=location.latitude if location else 0.0,
        longitude=location.longitude if location else 0.0,
        distance=landmark.distance,
        position=landmark.position,
        p_value=0.0,
        same_category_count_100m=None,
    )
    return ScoredPoi(
        poi=poi,
        p_h=0.0,
        u=0.0,
        d=0.0,
        s_final=landmark.score,
    )


def _build_selected_landmark(
    scored: ScoredPoi,
    is_open_map: dict[str, str],
) -> SelectedLandmark:
    """Serialize a scored POI into the public SelectedLandmark model."""
    is_open_status = _resolve_is_open_status(scored.poi, is_open_map)
    return SelectedLandmark(
        name=scored.poi.place_name,
        category_code=scored.poi.category_group_code,
        position=scored.poi.position,
        distance=scored.poi.distance,
        score=round(scored.s_final, 4),
        match_status="POI_ONLY",
        is_open=is_open_status == "OPEN",
        location=Location(
            latitude=scored.poi.latitude,
            longitude=scored.poi.longitude,
        ),
    )


def _build_crosswalk_guidance(
    existing: Guidance,
    before: ScoredPoi | None,
    after: ScoredPoi | None,
) -> Guidance:
    """Build crosswalk guidance that uses both before- and after-crossing POIs."""
    if before and after:
        primary = (
            f"{before.poi.place_name} 앞 횡단보도에서 "
            f"{after.poi.place_name} 쪽으로 건너세요."
        )
        pre_alert = f"곧 {before.poi.place_name} 앞 횡단보도가 나옵니다."
    elif before:
        primary = f"{before.poi.place_name} 앞 횡단보도를 건너세요."
        pre_alert = f"곧 {before.poi.place_name} 앞 횡단보도가 나옵니다."
    elif after:
        primary = f"횡단보도를 건너 {after.poi.place_name} 쪽으로 가세요."
        pre_alert = "곧 횡단보도가 나옵니다."
    else:
        primary = existing.primary
        pre_alert = existing.pre_alert

    return Guidance(
        primary=primary,
        pre_alert=pre_alert,
        action=existing.action,
    )


async def _build_route_response(request: RouteRequest) -> RouteResponse:
    """Full live pipeline: Tmap → DP extraction → midpoint → POI/scoring → RouteResponse."""
    tmap_result = await request_pedestrian_route(
        origin_lat=request.origin_lat,
        origin_lng=request.origin_lng,
        dest_lat=request.dest_lat,
        dest_lng=request.dest_lng,
        dest_name=request.dest_name or "목적지",
    )

    decision_points = extract_decision_points(tmap_result)

    print(f"\n{'='*60}")
    print(f"[STEP1] DP 추출 완료: {len(decision_points)}개")
    for dp in decision_points:
        print(f"  dp={dp.dp_id}, type={dp.dp_type}, turnType={dp.turn_type}, dist={dp.distance_from_start:.0f}m")
    print(f"{'='*60}")

    # Midpoint insertion — virtual DPs come back with landmark + guidance + panorama
    decision_points = await insert_midpoints(
        decision_points,
        tmap_result.coordinates,
    )

    print(f"\n[STEP2] Midpoint 삽입 후: {len(decision_points)}개")
    for dp in decision_points:
        lm = dp.selected_landmark.name if dp.selected_landmark else "NONE"
        g = dp.guidance.primary[:40] if dp.guidance else "NO_GUIDANCE"
        print(f"  dp={dp.dp_id}, type={dp.dp_type}, landmark={lm}, guidance={g}")
    print(f"{'='*60}")

    # ----- STEP 3: POI search + per-DP ranking (top-k candidates kept for STEP 4) -----
    # Build parallel arrays indexed by decision_points order.
    dp_candidates: list[list[ScoredPoi]] = []
    crosswalk_after_per_dp: dict[str, ScoredPoi | None] = {}
    is_open_per_dp: dict[str, dict[str, str]] = {}

    for dp in decision_points:
        if dp.dp_type == "VIRTUAL":
            # midpoint_service already chose a landmark; feed it as a single
            # fixed candidate so it participates in the sequence-dedup chain.
            if dp.selected_landmark is not None:
                dp_candidates.append([_scored_from_selected_landmark(dp.selected_landmark)])
            else:
                dp_candidates.append([])
            is_open_per_dp[dp.dp_id] = {}
            continue

        if dp.dp_type in ("DEPARTURE", "ARRIVAL"):
            dp_candidates.append([])
            is_open_per_dp[dp.dp_id] = {}
            continue

        bearing = _get_dp_bearing(dp, tmap_result.coordinates)

        if dp.dp_type == "CROSSWALK":
            crosswalk_result = await search_pois_for_crosswalk(
                dp.location.latitude,
                dp.location.longitude,
                bearing,
            )
            print(
                f"  [STEP3] CROSSWALK dp={dp.dp_id}: "
                f"before_pois={len(crosswalk_result.before)}, "
                f"after_pois={len(crosswalk_result.after)}"
            )
            combined_pois = crosswalk_result.before + crosswalk_result.after
            is_open_map = (
                await fetch_is_open_statuses(combined_pois)
                if combined_pois
                else {}
            )
            before_ranked = rank_pois(crosswalk_result.before, is_open_map)
            after_best = (
                select_landmark(crosswalk_result.after, is_open_map)
                if crosswalk_result.after
                else None
            )
            dp_candidates.append(before_ranked)
            crosswalk_after_per_dp[dp.dp_id] = after_best
            is_open_per_dp[dp.dp_id] = is_open_map
        else:
            pois = await search_pois_for_dp(
                dp.location.latitude,
                dp.location.longitude,
                bearing,
            )
            print(f"  [STEP3] {dp.dp_type} dp={dp.dp_id}: pois={len(pois)}")
            for p in pois[:5]:
                print(
                    f"    poi: {p.place_name} ({p.category_group_code}) "
                    f"dist={p.distance:.0f}m pos={p.position}"
                )
            is_open_map = await fetch_is_open_statuses(pois) if pois else {}
            ranked = rank_pois(pois, is_open_map)
            dp_candidates.append(ranked)
            is_open_per_dp[dp.dp_id] = is_open_map

    # ----- STEP 4: Sequence optimization (name dedup + direction consistency) -----
    optimized_landmarks = optimize_sequence(dp_candidates)

    print(f"\n{'='*60}")
    print(f"[STEP4] 시퀀스 최적화 결과 ({len(optimized_landmarks)}개)")
    print(f"{'='*60}")
    for dp, sel in zip(decision_points, optimized_landmarks):
        name = sel.poi.place_name if sel else "NONE"
        score = f"{sel.s_final:.2f}" if sel else "—"
        print(f"  dp={dp.dp_id}, type={dp.dp_type}, selected={name}, score={score}")
    print(f"{'='*60}")

    # ----- STEP 5: Apply optimized selection + panorama + guidance generation -----
    prev_landmark_name: str | None = None
    for i, dp in enumerate(decision_points):
        if dp.dp_type == "VIRTUAL":
            # midpoint_service finalized landmark+guidance+panorama already.
            if dp.selected_landmark is not None:
                prev_landmark_name = dp.selected_landmark.name
            else:
                prev_landmark_name = None
            continue

        selected = optimized_landmarks[i]
        is_open_map = is_open_per_dp.get(dp.dp_id, {})
        after_scored = crosswalk_after_per_dp.get(dp.dp_id)

        # Apply optimized selection to dp.selected_landmark.
        # CROSSWALK fallback: if before-crossing has no landmark, surface the
        # after-crossing one in the API output instead of leaving it null.
        if selected is not None:
            dp.selected_landmark = _build_selected_landmark(selected, is_open_map)
        elif dp.dp_type == "CROSSWALK" and after_scored is not None:
            dp.selected_landmark = _build_selected_landmark(after_scored, is_open_map)

        # Panorama: regular DPs (3-direction), DEPARTURE/ARRIVAL (front-only).
        if dp.panorama_request is None:
            if dp.dp_type in ("DEPARTURE", "ARRIVAL"):
                dp.panorama_request = PanoramaRequest(
                    location=dp.location,
                    directions=[
                        PanoramaDirection(
                            pan=0.0, label="FRONT", is_primary=True,
                        ),
                    ],
                )
            else:
                dp.panorama_request = _build_3dir_panorama(
                    dp.location, dp.turn_type,
                )

        # Guidance generation
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
                from constants import TURN_TYPE_TO_ACTION
                next_action = TURN_TYPE_TO_ACTION.get(next_tt)

        dp.guidance = generate_guidance(
            dp_type=dp.dp_type,
            turn_type=dp.turn_type,
            selected_landmark=selected,
            match_status="POI_ONLY" if selected else None,
            environment_desc=None,
            facility_visible=None,
            prev_landmark_name=prev_landmark_name,
            next_dp_distance=next_dp_distance,
            dest_name=request.dest_name or "",
            distance_from_start=dp.distance_from_start,
            next_action=next_action,
            after_landmark=after_scored,
            after_match_status="POI_ONLY" if after_scored else None,
            after_environment_desc=None,
            tmap_description=dp.tmap_description,
        )

        if selected is not None:
            prev_landmark_name = selected.poi.place_name
        elif dp.dp_type == "CROSSWALK" and after_scored is not None:
            prev_landmark_name = after_scored.poi.place_name
        else:
            prev_landmark_name = None

    print(f"\n{'='*60}")
    print(f"[STEP5] 최종 DP 상태 ({len(decision_points)}개)")
    print(f"{'='*60}")
    for dp in decision_points:
        lm = dp.selected_landmark.name if dp.selected_landmark else "NONE"
        pri = dp.guidance.primary[:50] if dp.guidance else "NO_GUIDANCE"
        pre = (dp.guidance.pre_alert[:40] if dp.guidance and dp.guidance.pre_alert else "null")
        print(f"[PIPE] dp={dp.dp_id}, type={dp.dp_type}, landmark={lm}")
        print(f"       primary={pri}")
        print(f"       preAlert={pre}")
    print(f"{'='*60}\n")

    route_id = f"route-{uuid.uuid4().hex[:10]}"
    origin = Location(latitude=request.origin_lat, longitude=request.origin_lng)
    destination = Location(latitude=request.dest_lat, longitude=request.dest_lng)

    return RouteResponse(
        route_id=route_id,
        origin=origin,
        destination=destination,
        dest_name=request.dest_name or "",
        total_distance=tmap_result.total_distance,
        total_time=tmap_result.total_time,
        decision_points=decision_points,
        route_line_string=[
            Location(latitude=lat, longitude=lon)
            for lat, lon in tmap_result.coordinates
        ],
        is_rerouted=False,
        previous_route_id=None,
    )


@app.post("/api/route", response_model=ApiResponse)
async def route_create(request: RouteRequest) -> ApiResponse:
    """Live pipeline: Tmap → DP → midpoint → POI/scoring → RouteResponse."""
    route_response = await _build_route_response(request)

    # Mock guidance override for demo route
    from config import MOCK_GUIDANCE
    if MOCK_GUIDANCE:
        from mock_guidance import apply_mock_guidance
        route_response = apply_mock_guidance(
            route_response,
            route_response.origin,
            route_response.destination,
        )

    # Generate Google Cloud TTS audio for all guidance texts
    route_response = await _attach_tts_audio(route_response)

    _route_cache[route_response.route_id] = route_response
    return ApiResponse(data=route_response)


@app.get("/api/route/{route_id}", response_model=ApiResponse)
def route_get(route_id: str) -> ApiResponse:
    """Retrieve a cached route by route_id. 404 if not found."""
    cached = _route_cache.get(route_id)
    if cached is None:
        raise HTTPException(status_code=404, detail="Route not found")
    return ApiResponse(data=cached)


# ---------------------------------------------------------------------------
# TTS endpoint (on-demand, for deviation warnings etc.)
# ---------------------------------------------------------------------------

@app.get("/api/tts")
async def tts_synthesize(text: str):
    """Synthesize a single text string to mp3 audio (base64)."""
    if not text:
        raise HTTPException(status_code=400, detail="text parameter is required")
    audio_b64 = await synthesize(text)
    if audio_b64 is None:
        raise HTTPException(status_code=502, detail="TTS synthesis failed")
    return {"audio": audio_b64}


# ---------------------------------------------------------------------------
# Deviation detection endpoint
# ---------------------------------------------------------------------------

class DeviationCheckRequest(BaseModel):
    """Lightweight deviation check request matching frontend WebSocket JSON."""
    route_id: str
    latitude: float
    longitude: float
    timestamp: str | float = ""
    speed: float = 0.0

    def epoch_timestamp(self) -> float:
        """Convert ISO string or epoch float to epoch seconds."""
        if isinstance(self.timestamp, (int, float)) and self.timestamp > 0:
            return float(self.timestamp)
        if isinstance(self.timestamp, str) and self.timestamp:
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))
                return dt.timestamp()
            except ValueError:
                pass
        import time
        return time.time()


def _get_or_create_detector(route_id: str) -> DeviationDetector:
    """Get existing detector or create one from the cached route."""
    if route_id in _detector_cache:
        return _detector_cache[route_id]

    route = _route_cache.get(route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")

    linestring = [
        (loc.latitude, loc.longitude) for loc in route.route_line_string
    ]
    detector = DeviationDetector(linestring)
    _detector_cache[route_id] = detector
    return detector


def _find_current_dp(
    lat: float, lng: float, route: RouteResponse, route_id: str,
    user_dfs: float,
) -> tuple[DecisionPoint, float, int, DecisionPoint | None]:
    """Find next uncompleted DP using distance_from_start progression.

    Returns (current_dp, haversine_dist, index, just_passed_dp).
    just_passed_dp is set when a DP was passed between this call and the last
    (distance_from_start exceeded) so the caller can fire ARRIVAL for it.
    """
    completed = _completed_dps.get(route_id, set())
    just_passed: DecisionPoint | None = None

    # Check only the NEXT uncompleted DP (skip last DP = destination)
    for dp in route.decision_points[:-1]:
        if dp.dp_id in completed:
            continue
        # First uncompleted DP — check if passed
        # Both conditions required to prevent projection overshoot:
        #   1) user_dfs exceeded dp's distance_from_start
        #   2) haversine distance is within 50m (was actually near the DP)
        dp_haver = haversine(lat, lng, dp.location.latitude, dp.location.longitude)
        if user_dfs > dp.distance_from_start and dp_haver < 20.0:
            completed.add(dp.dp_id)
            just_passed = dp
        break  # only check one DP per call

    # Return first uncompleted DP
    for i, dp in enumerate(route.decision_points):
        if dp.dp_id in completed:
            continue
        d = haversine(lat, lng, dp.location.latitude, dp.location.longitude)
        return dp, d, i, just_passed

    # All completed — fall back to last DP
    last = route.decision_points[-1]
    d = haversine(lat, lng, last.location.latitude, last.location.longitude)
    return last, d, len(route.decision_points) - 1, just_passed


def _deviation_result_to_response(
    result: DeviationResult,
    route_id: str,
    lat: float,
    lng: float,
    route: RouteResponse | None,
) -> DeviationResponse:
    """Convert internal DeviationResult to API DeviationResponse."""
    state_mapping = {
        "NORMAL": "ON_ROUTE",
        "SUSPECTED": "DEVIATION_SUSPECTED",
        "WARNING": "DEVIATION_WARNING",
        "DEVIATED": "DEVIATION_CONFIRMED",
        "CONFIRMING": "DEVIATION_WARNING",
        "RETURNING": "RETURNING",
    }
    navigation_state = state_mapping.get(result.state, "ON_ROUTE")

    trigger: str | None = None
    guidance: Guidance | None = None

    # Deviation-related triggers
    if result.message:
        if "벗어난" in result.message:
            trigger = "DEVIATION_WARNING"
        elif "다시 찾고" in result.message:
            trigger = "REROUTING"
        elif "돌아오고" in result.message:
            trigger = "RETURN_DETECTED"
        guidance = Guidance(primary=result.message)

    current_dp_id = ""
    distance_to_dp = result.distance_to_route_m
    progress: Progress | None = None

    if route and navigation_state == "ON_ROUTE":
        if route_id not in _completed_dps:
            _completed_dps[route_id] = set()

        # Compute user's distance_from_start for pass-through detection
        linestring = [
            (loc.latitude, loc.longitude) for loc in route.route_line_string
        ]
        user_dfs = project_distance_on_linestring(lat, lng, linestring)

        dp, dist, idx, just_passed = _find_current_dp(
            lat, lng, route, route_id, user_dfs,
        )
        current_dp_id = dp.dp_id
        distance_to_dp = dist

        print(f"[DP-DEBUG] gps=({lat:.6f},{lng:.6f}), user_dfs={user_dfs:.1f}, "
              f"current_dp={current_dp_id}, dp_dfs={dp.distance_from_start:.1f}, "
              f"haversine={dist:.1f}, just_passed={just_passed.dp_id if just_passed else None}")

        # Check destination arrival first
        dest = route.decision_points[-1]
        dest_dist = haversine(lat, lng, dest.location.latitude, dest.location.longitude)
        if dest_dist <= ARRIVAL_DISTANCE or (user_dfs >= dest.distance_from_start and dest_dist < 20.0):
            navigation_state = "ARRIVED"
            trigger = "ARRIVAL"
            guidance = Guidance(
                primary=dest.guidance.primary,
                pre_alert=dest.guidance.pre_alert,
                action=dest.guidance.action,
            )
            current_dp_id = dest.dp_id
            _completed_dps[route_id].add(dest.dp_id)
        elif just_passed is not None:
            # A DP was passed (distance_from_start exceeded) — fire ARRIVAL
            trigger = "ARRIVAL"
            guidance = Guidance(
                primary=just_passed.guidance.primary,
                pre_alert=just_passed.guidance.pre_alert,
                action=just_passed.guidance.action,
            )
        else:
            # DP proximity trigger (haversine-based)
            if dist <= ARRIVAL_DISTANCE:
                trigger = "ARRIVAL"
                guidance = Guidance(
                    primary=dp.guidance.primary,
                    pre_alert=dp.guidance.pre_alert,
                    action=dp.guidance.action,
                )
                _completed_dps[route_id].add(dp.dp_id)
            elif dist <= PRE_ALERT_DISTANCE:
                trigger = "PRE_ALERT"
                guidance = Guidance(
                    primary=dp.guidance.pre_alert or dp.guidance.primary,
                    pre_alert=dp.guidance.pre_alert,
                    action=dp.guidance.action,
                )

        # Build progress
        completed = [d.dp_id for d in route.decision_points if d.dp_id in _completed_dps[route_id]]
        remaining = [d.dp_id for d in route.decision_points if d.dp_id not in _completed_dps[route_id]]
        dest_loc = route.decision_points[-1].location
        dist_remaining = haversine(lat, lng, dest_loc.latitude, dest_loc.longitude)
        progress = Progress(
            completed_dps=completed,
            current_dp_id=current_dp_id,
            remaining_dps=remaining,
            distance_remaining=dist_remaining,
            time_remaining=dist_remaining / WALKING_SPEED_MPS,
        )
    elif route:
        current_dp_id = route.decision_points[0].dp_id

    return DeviationResponse(
        navigation_state=navigation_state,
        current_dp_id=current_dp_id,
        distance_to_dp=distance_to_dp,
        trigger=trigger,
        guidance=guidance,
        progress=progress,
    )


@app.post("/api/deviation", response_model=ApiResponse)
def deviation_check(request: DeviationCheckRequest) -> ApiResponse:
    """Real-time deviation check. Creates detector on first call per route."""
    detector = _get_or_create_detector(request.route_id)

    gps = GpsReading(
        lat=request.latitude,
        lng=request.longitude,
        timestamp=request.epoch_timestamp(),
    )
    result = detector.update(gps)
    print(f"[DEV-DEBUG] state={result.state}, dist={result.distance_to_route_m:.1f}, gps_error={result.gps_error}, msg={result.message}")

    route = _route_cache.get(request.route_id)

    return ApiResponse(data=_deviation_result_to_response(
        result, request.route_id, request.latitude, request.longitude, route,
    ))


# ---------------------------------------------------------------------------
# Reroute endpoint
# ---------------------------------------------------------------------------

@app.post("/api/reroute", response_model=ApiResponse)
async def reroute_endpoint(request: RerouteRequest) -> ApiResponse:
    """Re-route from current GPS to destination. Reuses previous DP cache."""
    # Fetch previous DPs from cache if previous_route_id exists
    previous_dps = None
    if request.previous_route_id:
        prev_route = _route_cache.get(request.previous_route_id)
        if prev_route is not None:
            previous_dps = prev_route.decision_points

    result = await reroute_service(request, previous_dps=previous_dps)

    if result.success and result.route_response is not None:
        new_route_id = result.route_response.route_id
        # Cache the new route
        _route_cache[new_route_id] = result.route_response
        # Create new detector for the new route and remove old one
        new_linestring = [
            (loc.latitude, loc.longitude)
            for loc in result.route_response.route_line_string
        ]
        _detector_cache[new_route_id] = DeviationDetector(new_linestring)
        _completed_dps[new_route_id] = set()
        if request.previous_route_id and request.previous_route_id in _detector_cache:
            del _detector_cache[request.previous_route_id]
        if request.previous_route_id and request.previous_route_id in _completed_dps:
            del _completed_dps[request.previous_route_id]

    return ApiResponse(data=result)


# ---------------------------------------------------------------------------
# Conversation endpoint (Mode B)
# ---------------------------------------------------------------------------

@app.post("/api/chat", response_model=ApiResponse)
async def chat_endpoint(request: ConversationRequest) -> ApiResponse:
    """Mode B conversational guidance. Answers questions about the current route."""
    route = _route_cache.get(request.route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")

    result = await conversation_chat(request, route)
    return ApiResponse(data=result)


def _get_dp_bearing(
    dp: DecisionPoint,
    route_coordinates: list[tuple[float, float]],
) -> float:
    """Calculate travel bearing at a DP location on the route."""
    from geo import point_to_segment_distance

    if len(route_coordinates) < 2:
        return 0.0

    min_dist = float("inf")
    best_idx = 0
    for i in range(len(route_coordinates) - 1):
        d = point_to_segment_distance(
            dp.location.latitude, dp.location.longitude,
            route_coordinates[i][0], route_coordinates[i][1],
            route_coordinates[i + 1][0], route_coordinates[i + 1][1],
        )
        if d < min_dist:
            min_dist = d
            best_idx = i

    return calculate_bearing(
        route_coordinates[best_idx][0], route_coordinates[best_idx][1],
        route_coordinates[best_idx + 1][0], route_coordinates[best_idx + 1][1],
    )
