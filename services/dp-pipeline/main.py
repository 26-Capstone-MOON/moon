"""FastAPI app for the live MOON dp-pipeline."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from constants import (
    ARRIVAL_DISTANCE,
    PRE_ALERT_DISTANCE,
)
from dp_extractor import extract_decision_points
from geo import (
    haversine,
    project_distance_on_linestring,
)
from midpoint_service import insert_midpoints
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
    Progress,
    RouteRequest,
    RouteResponse,
)
from tts_service import synthesize
from pipeline_runner import (
    get_dp_bearing,
    run_pipeline_steps_3_to_5,
)
from tmap_service import request_pedestrian_route
from config import settings
from vision_schemas import VisionAnalysisData, VisionAnalysisStatus, VisionAnalyzeRequest
from vision_service import analyze_panorama
from vision_cache import attach_visual_context_to_route, put_visual_context

WALKING_SPEED_MPS = 1.2

# ---------------------------------------------------------------------------
# In-memory route cache
# ---------------------------------------------------------------------------
_route_cache: dict[str, RouteResponse] = {}

# ---------------------------------------------------------------------------
# In-memory TTS cache (text -> base64 mp3)
# ---------------------------------------------------------------------------
_tts_cache: dict[str, str] = {}

# ---------------------------------------------------------------------------
# In-memory DeviationDetector session cache
# ---------------------------------------------------------------------------
_detector_cache: dict[str, DeviationDetector] = {}

# ---------------------------------------------------------------------------
# Per-route completed DP tracking (dp_id set)
# ---------------------------------------------------------------------------
_completed_dps: dict[str, set[str]] = {}

class PanoramaResultsUploadRequest(BaseModel):
    dp_id: str
    direction: str
    image_base64: Optional[str] = None
    selected_landmark: Optional[dict] = None
    candidate_name: Optional[str] = None
    candidate_type: Optional[str] = None
    analysis_purpose: Optional[str] = None
    analysis_result: Optional[VisionAnalysisData] = None


app = FastAPI(
    title="MOON dp-pipeline server",
    version="0.1.0",
    description="Live route, guidance, tracking, and Vision endpoints.",
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
        bearing = get_dp_bearing(dp, tmap_result.coordinates)

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
                "/api/deviation",
                "/api/reroute",
                "/api/chat",
                "/api/vision/analyze",
            ],
        }
    )


@app.get("/health", response_model=ApiResponse)
def health() -> ApiResponse:
    return ApiResponse(data={"status": "ok"})


@app.post("/api/vision/analyze", response_model=ApiResponse)
async def vision_analyze(request: VisionAnalyzeRequest) -> ApiResponse:
    result = await analyze_panorama(request)
    if result.analysis_status == VisionAnalysisStatus.VISION_DISABLED:
        raise HTTPException(status_code=503, detail="Vision analysis is disabled")
    return ApiResponse(data=result)


@app.post("/api/route/{route_id}/panorama-results", response_model=ApiResponse)
async def panorama_results_upload(route_id: str, request: PanoramaResultsUploadRequest) -> ApiResponse:
    selected_landmark = request.selected_landmark or {}
    candidate_name = request.candidate_name or selected_landmark.get("name")
    candidate_type = request.candidate_type or selected_landmark.get("category_code")
    route = _route_cache.get(route_id)
    dp_location = None
    if route is not None:
        for dp in route.decision_points:
            if dp.dp_id == request.dp_id:
                dp_location = dp.location
                break

    if request.analysis_result is not None:
        result = request.analysis_result
    else:
        analyze_request = VisionAnalyzeRequest(
            route_id=route_id,
            dp_id=request.dp_id,
            direction=request.direction,
            image_base64=request.image_base64,
            selected_landmark=request.selected_landmark,
            analysis_purpose=request.analysis_purpose or "SURROUNDING",
        )
        result = await analyze_panorama(analyze_request)
        if result.analysis_status == VisionAnalysisStatus.VISION_DISABLED:
            raise HTTPException(status_code=503, detail="Vision analysis is disabled")

    persisted = put_visual_context(
        route_id,
        request.dp_id,
        request.direction,
        result,
        candidate_name=candidate_name,
        candidate_type=candidate_type,
        source="panorama-results",
        location=dp_location,
    )

    route_updated = False
    route_recalculated = False
    if route is not None:
        if settings.kakao_api_key:
            snapshot = route.model_copy(deep=True)
            try:
                await run_pipeline_steps_3_to_5(
                    decision_points=route.decision_points,
                    route_coordinates=[
                        (loc.latitude, loc.longitude)
                        for loc in route.route_line_string
                    ],
                    dest_name=route.dest_name,
                    route_id=route.route_id,
                )
                route_updated = True
                route_recalculated = True
            except Exception:
                _route_cache[route_id] = snapshot
                route = snapshot
                route_updated = attach_visual_context_to_route(route, request.dp_id)
        else:
            route_updated = attach_visual_context_to_route(route, request.dp_id)

    return ApiResponse(data={
        **persisted.model_dump(mode="json"),
        "route_cache_updated": route_updated,
        "route_recalculated": route_recalculated,
    })


@app.post("/api/smoke/tmap", response_model=ApiResponse)
async def tmap_smoke(request: RouteRequest) -> ApiResponse:
    return ApiResponse(
        data=await _build_live_pipeline_summary(
            request,
            scenario="tmap_live_dp_pipeline",
        )
    )


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

async def _build_route_response(request: RouteRequest) -> RouteResponse:
    """Full live pipeline: Tmap → DP extraction → midpoint → POI/scoring → RouteResponse."""
    route_id = f"route-{uuid.uuid4().hex[:10]}"
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

    # ----- STEP 3-5: POI scoring → sequence optimization → panorama + guidance -----
    await run_pipeline_steps_3_to_5(
        decision_points=decision_points,
        route_coordinates=tmap_result.coordinates,
        dest_name=request.dest_name or "",
        route_id=route_id,
    )

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
    cached_audio = _tts_cache.get(text)
    if cached_audio is not None:
        return {"audio": cached_audio, "cached": True}

    audio_b64 = await synthesize(text)
    if audio_b64 is None:
        raise HTTPException(status_code=502, detail="TTS synthesis failed")

    _tts_cache[text] = audio_b64
    return {"audio": audio_b64, "cached": False}


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
        # Complete only when within ARRIVAL_DISTANCE (10m) — same threshold as ARRIVAL trigger
        dp_haver = haversine(lat, lng, dp.location.latitude, dp.location.longitude)
        if user_dfs > dp.distance_from_start and dp_haver <= ARRIVAL_DISTANCE:
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
        # When a DP was just passed in this tick, keep current_dp_id pointing at
        # the just-passed DP so the ARRIVAL trigger and currentDpId stay 1:1
        # aligned. The next tick will advance current_dp_id to the next DP.
        if just_passed is not None:
            current_dp_id = just_passed.dp_id
            distance_to_dp = haversine(
                lat, lng,
                just_passed.location.latitude, just_passed.location.longitude,
            )
        else:
            current_dp_id = dp.dp_id
            distance_to_dp = dist

        print(f"[DP-DEBUG] gps=({lat:.6f},{lng:.6f}), user_dfs={user_dfs:.1f}, "
              f"current_dp={current_dp_id}, next_dp={dp.dp_id}, "
              f"dp_dfs={dp.distance_from_start:.1f}, haversine={dist:.1f}, "
              f"just_passed={just_passed.dp_id if just_passed else None}")

        # Check destination arrival first
        dest = route.decision_points[-1]
        dest_dist = haversine(lat, lng, dest.location.latitude, dest.location.longitude)
        if dest_dist <= ARRIVAL_DISTANCE:
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

    # 클라이언트가 명시적으로 보낸 completed_dp_ids 우선,
    # 없으면 WebSocket /tracking이 누적해 둔 서버 캐시 폴백
    if request.completed_dp_ids is not None:
        completed = set(request.completed_dp_ids)
    else:
        completed = _completed_dps.get(request.route_id)
    result = await conversation_chat(request, route, completed)
    return ApiResponse(data=result)
