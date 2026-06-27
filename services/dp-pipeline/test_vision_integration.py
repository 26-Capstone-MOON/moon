from __future__ import annotations

from conversation_service import _build_route_context
from guidance_generator import generate_guidance
from poi_service import PoiResult
from schemas import DecisionPoint, Guidance, Location, RouteResponse, SelectedLandmark
from scoring_service import ScoredPoi, score_poi
from vision_cache import (
    _PERSISTED_VISION_CACHE,
    get_visual_context,
    put_visual_context,
)
from vision_schemas import VisionAnalysisData, VisionAnalysisStatus


def _poi(name: str = "GS25 역삼로점") -> PoiResult:
    return PoiResult(
        place_name=name,
        category_group_code="CS2",
        category_name="편의점",
        latitude=37.1,
        longitude=127.1,
        distance=20.0,
        position="RIGHT",
        p_value=0.8,
        same_category_count_100m=1,
    )


def _visual(name: str = "GS25 역삼로점") -> VisionAnalysisData:
    return VisionAnalysisData(
        analysis_status=VisionAnalysisStatus.ANALYZED,
        candidate_name=name,
        candidate_type="STORE",
        color_distinctiveness=0.5,
        text_sign_ratio=0.4,
        appearance_description="파란색 간판이 보이는 매장",
        scene_description="전방에 간판과 횡단보도가 보입니다.",
        has_crosswalk=True,
    )


def setup_function():
    _PERSISTED_VISION_CACHE.clear()


def test_vision_v_is_applied_to_final_score_when_cached():
    poi = _poi()
    put_visual_context("route-1", "dp-1", "RIGHT", _visual(), candidate_name=poi.place_name)

    scored = score_poi(poi, [poi], "OPEN", route_id="route-1", dp_id="dp-1")

    assert scored.v == 0.2
    assert scored.s_final == scored.p_h * scored.u * scored.v * scored.d
    assert scored.visual_context is not None


def test_score_falls_back_to_legacy_formula_without_vision():
    poi = _poi()

    scored = score_poi(poi, [poi], "OPEN", route_id="route-1", dp_id="dp-1")

    assert scored.v is None
    assert scored.s_final == scored.p_h * scored.u * scored.d


def test_guidance_optionally_includes_appearance_description():
    poi = _poi()
    scored = ScoredPoi(
        poi=poi,
        p_h=0.8,
        u=1.0,
        d=0.8,
        s_final=0.128,
        v=0.2,
        visual_context=_visual(),
    )

    guidance = generate_guidance(
        dp_type="DIRECTION_CHANGE",
        turn_type=13,
        selected_landmark=scored,
        match_status="POI_ONLY",
        environment_desc=scored.visual_context.appearance_description,
        facility_visible=None,
        prev_landmark_name=None,
        next_dp_distance=30.0,
    )

    assert "파란색 간판이 보이는 매장" in guidance.primary


def _route(with_visual: bool) -> RouteResponse:
    visual = _visual() if with_visual else None
    landmark = SelectedLandmark(
        name="GS25 역삼로점",
        category_code="CS2",
        position="RIGHT",
        distance=20.0,
        score=1.0,
        match_status="POI_ONLY",
        appearance=visual.appearance_description if visual else None,
        visual_context=visual,
    )
    dp = DecisionPoint(
        dp_id="dp-1",
        dp_type="DIRECTION_CHANGE",
        turn_type=13,
        location=Location(latitude=37.1, longitude=127.1),
        distance_from_start=10.0,
        guidance=Guidance(primary="GS25 역삼로점을 끼고 우회전하세요.", action="RIGHT_TURN"),
        selected_landmark=landmark,
    )
    return RouteResponse(
        route_id="route-1",
        origin=Location(latitude=37.0, longitude=127.0),
        destination=Location(latitude=37.2, longitude=127.2),
        total_distance=100.0,
        total_time=80.0,
        decision_points=[dp],
        route_line_string=[],
    )


def test_visual_context_is_included_in_conversation_context():
    context = _build_route_context(_route(with_visual=True), "dp-1", set())

    assert "visual context" in context
    assert "파란색 간판이 보이는 매장" in context


def test_conversation_context_keeps_poi_only_fallback_without_visual_context():
    context = _build_route_context(_route(with_visual=False), "dp-1", set())

    assert "GS25 역삼로점" in context
    assert "visual context" not in context


def test_cached_vision_result_is_reused_for_same_dp_direction_candidate():
    original = put_visual_context("route-1", "dp-1", "RIGHT", _visual(), candidate_name="GS25 역삼로점")
    reused = get_visual_context("route-1", "dp-1", "RIGHT", "GS25 역삼로점")

    assert reused is original


def test_spatial_vision_cache_can_be_used_before_new_route_id_is_known():
    poi = _poi()
    dp_location = Location(latitude=37.1, longitude=127.1)
    put_visual_context(
        "previous-route",
        "previous-dp",
        "RIGHT",
        _visual(),
        candidate_name=poi.place_name,
        location=dp_location,
    )

    scored = score_poi(
        poi,
        [poi],
        "OPEN",
        route_id="new-route",
        dp_id="new-dp",
        dp_location=dp_location,
    )

    assert scored.v == 0.2
