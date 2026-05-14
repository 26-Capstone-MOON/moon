"""Mock guidance for 최종발표용 데모 루트 (버거킹 신논현역점 → 스타벅스 강남에비뉴점).

When MOCK_GUIDANCE=True, pipeline-generated guidance is replaced with
hand-crafted Korean text. Only the guidance field is overwritten — coordinates,
distance, landmarks, panorama data all remain from the real pipeline.

This file extends the original mock_guidance.py logic so that arbitrary DP
types (not just VIRTUAL) can be inserted, via _insert_extra_dps() driven by
_EXTRA_INSERT_SPECS.
"""

from __future__ import annotations

import logging
import uuid

from geo import haversine
from schemas import (
    DecisionPoint,
    Guidance,
    Location,
    PanoramaDirection,
    PanoramaRequest,
    RouteResponse,
    SelectedLandmark,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Demo route coordinates
# ---------------------------------------------------------------------------

DEMO_ROUTE_ORIGIN = (37.504879, 127.025111)   # 버거킹 신논현역점
DEMO_ROUTE_DEST   = (37.502550, 127.024091)   # 스타벅스 강남에비뉴점

_MATCH_THRESHOLD_M = 100.0  # origin/dest must be within 100m to apply mock

# Pipeline produces 6 DPs originally; we drop pipeline DP2 (아디다스) to get 5,
# then insert 1 extra DP (GS칼텍스) to reach the 6 mock entries.
_EXPECTED_PIPELINE_DP_COUNT = 5

# ---------------------------------------------------------------------------
# Mock guidance data — 6 DPs in order
# Pipeline (after 아디다스 제거) produces 5 DPs. 1 extra DP (GS칼텍스) is
# inserted at mock_index 3.
# Each entry: (dp_type, landmark_name, primary, pre_alert, action)
#   dp_type is for reference/logging only; matching is purely by order.
# ---------------------------------------------------------------------------

MOCK_GUIDANCES: list[dict] = [
    # DP0: DEPARTURE (pipeline 0)
    {
        "dp_type": "DEPARTURE",
        "landmark_name": "버거킹 신논현역점",
        "landmark_lat": 37.504917,
        "landmark_lng": 127.025027,
        "dp_marker_lat": 37.504805,
        "dp_marker_lng": 127.025133,
        "pan_override": 328.5,
        "primary": "버거킹 신논현역점에서 출발합니다.",
        "pre_alert": None,
        "action": None,
        "appearance": "빨간색 'BURGER KING' 간판이 눈에 띄는 매장이에요. 통유리로 된 빌딩 1층에 있어요.",
    },
    # DP1: CROSSWALK (pipeline 1)
    {
        "dp_type": "CROSSWALK",
        "landmark_name": "팀홀튼 신논현역점",
        "landmark_lat": 37.504806,
        "landmark_lng": 127.024790,
        "dp_marker_lat": 37.504735,
        "dp_marker_lng": 127.024800,
        "pan_override": 354.3,
        "primary": "[팀홀튼 신논현역점 방면으로 횡단보도 건너기 안내]",
        "pre_alert": "[횡단보도 곧 나옴 사전 알림]",
        "action": "CROSSWALK",
        "appearance": "흰색 외관에 크고 작은 동그란 구멍이 빼곡하게 뚫린 독특한 디자인의 건물이에요.",
    },
    # DP2: CROSSWALK (pipeline 2, was pipeline 3 before 아디다스 제거)
    {
        "dp_type": "CROSSWALK",
        "landmark_name": "교보타워 방향 횡단보도",
        "landmark_lat": 37.504027,
        "landmark_lng": 127.024286,
        "dp_marker_lat": 37.504341,
        "dp_marker_lng": 127.024922,
        "pan_override": None,
        "primary": "[교보타워 방면으로 횡단보도 건너기 안내]",
        "pre_alert": "[횡단보도 곧 나옴 사전 알림]",
        "action": "CROSSWALK",
        "appearance": "강남대로 큰 사거리의 횡단보도예요. 길 건너편에 빨간 외관의 교보타워가 보여요.",
    },
    # DP3: DIRECTION_CHANGE — 삽입 (pipeline DP2와 DP3 사이)
    {
        "dp_type": "DIRECTION_CHANGE",
        "landmark_name": "GS칼텍스 삼방주유소",
        "landmark_lat": 37.503805,
        "landmark_lng": 127.023270,
        "dp_marker_lat": 37.503884,
        "dp_marker_lng": 127.023206,
        "pan_override": 161.1,
        "primary": "[GS칼텍스에서 좌회전 안내]",
        "pre_alert": "[GS칼텍스 보이면 좌회전 준비 사전 알림]",
        "action": "LEFT_TURN",
        "appearance": "'energy hub GS칼텍스' 간판의 주유소예요. 한쪽에 banapresso 카페가 함께 있어요.",
    },
    # DP4: CROSSWALK — 테이블나인 방향 횡단보도 (pipeline DP3 위치를 overwrite)
    {
        "dp_type": "CROSSWALK",
        "landmark_name": "테이블나인",
        "landmark_lat": 37.502967,
        "landmark_lng": 127.023442,
        "dp_marker_lat": 37.502911,
        "dp_marker_lng": 127.023368,
        "pan_override": 54.5,
        "primary": "[테이블나인 방면으로 횡단보도 건너기 안내]",
        "pre_alert": "[횡단보도 곧 나옴 사전 알림]",
        "action": "CROSSWALK",
        "appearance": "'TABLE NINE' 간판이 걸린 매장이에요. 'BUSINESS CENTER' 빌딩 1층에 입점되어 있어요.",
    },
    # DP5: ARRIVAL (pipeline 4, was pipeline 5 before 아디다스 제거)
    {
        "dp_type": "ARRIVAL",
        "landmark_name": "스타벅스 강남에비뉴점",
        "landmark_lat": 37.502550,
        "landmark_lng": 127.024091,
        "dp_marker_lat": 37.502478,
        "dp_marker_lng": 127.024073,
        "pan_override": None,
        "primary": "목적지 스타벅스 강남에비뉴점 도착했습니다.",
        "pre_alert": None,
        "action": None,
        "appearance": "초록색 'STARBUCKS' 간판이 보이는 카페예요. 유리벽으로 된 건물 1층에 자리잡고 있어요.",
    },
]

# ---------------------------------------------------------------------------
# Extra DP insertion specs.
# Each spec: dp_type can be any type (not just VIRTUAL).
# Maps mock_index → (before_pipeline_index, after_pipeline_index, fixed coords).
# ---------------------------------------------------------------------------

_EXTRA_INSERT_SPECS: list[dict] = [
    # GS칼텍스 DIRECTION_CHANGE — pipeline DP2(교보타워 횡단보도)와 DP3(테이블나인) 사이에 삽입
    {
        "mock_index": 3,
        "dp_type": "DIRECTION_CHANGE",
        "before_pipeline": 2,
        "after_pipeline": 3,
        "fixed_lat": 37.503884,
        "fixed_lng": 127.023206,
    },
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def apply_mock_guidance(
    route_response: RouteResponse,
    origin: Location,
    dest: Location,
) -> RouteResponse:
    """Overwrite guidance with hand-crafted demo text if route matches.

    Pipeline originally produces 6 DPs. We drop pipeline DP2 (아디다스) to
    normalize to 5, insert 1 extra DP (GS칼텍스), and overwrite all guidance
    to reach the 6 mock entries.

    Returns the (possibly mutated) RouteResponse.
    """
    if not _is_demo_route(origin, dest):
        logger.info("[MOCK_FINAL] Route does not match demo route — skipping mock guidance")
        return route_response

    dps = route_response.decision_points
    n_pipeline = len(dps)
    n_mock = len(MOCK_GUIDANCES)
    n_extra = len(_EXTRA_INSERT_SPECS)

    logger.info(
        "[MOCK_FINAL] Demo route matched! Pipeline DPs=%d, Mock entries=%d (expected_pipeline=%d, extra=%d)",
        n_pipeline, n_mock, _EXPECTED_PIPELINE_DP_COUNT, n_extra,
    )

    # Pipeline 원본(6개)이면 index 2(아디다스) 제거하여 5개로 정규화
    if n_pipeline == _EXPECTED_PIPELINE_DP_COUNT + 1:
        del route_response.decision_points[2]
        logger.info("[MOCK_FINAL] Removed pipeline DP at index 2 (아디다스 제거)")
        dps = route_response.decision_points
        n_pipeline = len(dps)

    # 정규화된 케이스: 5개 → extra 1개 삽입 → 6개로 mock에 맞춤
    if n_pipeline == _EXPECTED_PIPELINE_DP_COUNT:
        _insert_extra_dps(route_response)
        _overwrite_guidance(route_response.decision_points, MOCK_GUIDANCES)
        return route_response

    # Pipeline already has the same count as mock (extras already present)
    if n_pipeline == n_mock:
        _overwrite_guidance(dps, MOCK_GUIDANCES)
        return route_response

    # Fallback: overwrite as many as we can
    count = min(n_pipeline, n_mock)
    logger.warning(
        "[MOCK_FINAL] DP count mismatch (pipeline=%d, mock=%d). "
        "Overwriting first %d DPs only.",
        n_pipeline, n_mock, count,
    )
    _overwrite_guidance(dps, MOCK_GUIDANCES[:count])
    return route_response


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_demo_route(origin: Location, dest: Location) -> bool:
    """Check if origin and dest are within threshold of demo route."""
    d_origin = haversine(
        origin.latitude, origin.longitude,
        DEMO_ROUTE_ORIGIN[0], DEMO_ROUTE_ORIGIN[1],
    )
    d_dest = haversine(
        dest.latitude, dest.longitude,
        DEMO_ROUTE_DEST[0], DEMO_ROUTE_DEST[1],
    )
    return d_origin <= _MATCH_THRESHOLD_M and d_dest <= _MATCH_THRESHOLD_M


def _overwrite_guidance(
    dps: list[DecisionPoint],
    mocks: list[dict],
) -> None:
    """Replace guidance and selected_landmark for each DP from mock list."""
    for i, mock in enumerate(mocks):
        if i >= len(dps):
            break
        # Mock의 dp_type이 명시되어 있으면 함께 overwrite.
        # 프론트는 dp_type을 헤더 라벨링 등에 쓰므로 일관성 필요.
        mock_dp_type = mock.get("dp_type")
        if mock_dp_type and dps[i].dp_type != mock_dp_type:
            logger.info(
                "[MOCK_FINAL] DP%d dp_type %s → %s (overwritten by mock)",
                i, dps[i].dp_type, mock_dp_type,
            )
            dps[i].dp_type = mock_dp_type
            dps[i].turn_type = None  # mock dp_type과 충돌 가능성 제거
        dps[i].guidance = Guidance(
            primary=mock["primary"],
            pre_alert=mock.get("pre_alert"),
            action=mock.get("action"),
        )
        lm_name = mock.get("landmark_name")
        if lm_name:
            lm_lat = mock.get("landmark_lat")
            lm_lng = mock.get("landmark_lng")
            lm_location = Location(latitude=lm_lat, longitude=lm_lng) if lm_lat and lm_lng else None
            dps[i].selected_landmark = SelectedLandmark(
                name=lm_name,
                category_code="MOCK",
                position="FRONT",
                distance=0.0,
                score=1.0,
                match_status="POI_ONLY",
                is_open=True,
                location=lm_location,
                appearance=mock.get("appearance"),
            )
        else:
            dps[i].selected_landmark = None
        # Override DP marker location and panorama location with dp_marker_lat/lng.
        # Map marker (DpMarker.tsx) reads dp.location directly — for pipeline
        # pass-through DPs we rewrite it so the marker lands on the polyline.
        # SelectedLandmark.location (label) keeps landmark_lat/lng separately.
        marker_lat = mock.get("dp_marker_lat")
        marker_lng = mock.get("dp_marker_lng")
        if marker_lat is not None and marker_lng is not None:
            dps[i].location = Location(latitude=marker_lat, longitude=marker_lng)
            if dps[i].panorama_request is not None:
                dps[i].panorama_request.location = Location(
                    latitude=marker_lat, longitude=marker_lng
                )
            logger.info(
                "[MOCK_FINAL] DP%d marker/panorama location overridden to (%.6f, %.6f)",
                i, marker_lat, marker_lng,
            )
        # Apply pan_override to panoramaRequest
        pan_val = mock.get("pan_override")
        if pan_val is not None and dps[i].panorama_request is not None:
            dps[i].panorama_request.pan_override = pan_val
        logger.info(
            "[MOCK_FINAL] DP%d (%s) landmark=%s pan_override=%s → %s",
            i, dps[i].dp_type, lm_name or "null",
            pan_val if pan_val is not None else "none",
            mock["primary"][:40],
        )


def _insert_extra_dps(route_response: RouteResponse) -> None:
    """Insert extra DPs (any dp_type) at predefined positions between pipeline DPs.

    Inserts are done in reverse order (highest index first) so that earlier
    indices remain valid after each insertion.

    Coordinates: midpoint of surrounding DPs, unless fixed_lat/fixed_lng specified.
    distance_from_start: always interpolated from surrounding DPs.
    dp_type: taken from spec["dp_type"] (not hardcoded).
    """
    dps = route_response.decision_points

    # Sort specs by before_pipeline descending so insertions don't shift indices
    specs = sorted(_EXTRA_INSERT_SPECS, key=lambda s: (s["before_pipeline"], s["mock_index"]), reverse=True)

    for spec in specs:
        before_idx = spec["before_pipeline"]
        after_idx = spec["after_pipeline"]
        mock_idx = spec["mock_index"]
        dp_type = spec["dp_type"]

        if before_idx >= len(dps) or after_idx >= len(dps):
            logger.warning(
                "[MOCK_FINAL] Cannot insert %s at mock_index=%d: "
                "pipeline has only %d DPs (need indices %d and %d)",
                dp_type, mock_idx, len(dps), before_idx, after_idx,
            )
            continue

        dp_before = dps[before_idx]
        dp_after = dps[after_idx]

        # Use hardcoded coordinates if specified, otherwise midpoint
        vdp_lat = spec.get("fixed_lat")
        vdp_lng = spec.get("fixed_lng")
        if vdp_lat is None or vdp_lng is None:
            vdp_lat = (dp_before.location.latitude + dp_after.location.latitude) / 2
            vdp_lng = (dp_before.location.longitude + dp_after.location.longitude) / 2

        mid_dist = (dp_before.distance_from_start + dp_after.distance_from_start) / 2

        extra_dp = DecisionPoint(
            dp_id=f"dp-extra-mock-{uuid.uuid4().hex[:6]}",
            dp_type=dp_type,
            turn_type=None,
            location=Location(latitude=vdp_lat, longitude=vdp_lng),
            distance_from_start=mid_dist,
            guidance=Guidance(primary="", pre_alert=None, action=None),
            panorama_request=PanoramaRequest(
                location=Location(latitude=vdp_lat, longitude=vdp_lng),
                directions=[PanoramaDirection(pan=0.0, label="FRONT", is_primary=True)],
            ),
        )

        insert_pos = after_idx  # insert before the "after" DP
        dps.insert(insert_pos, extra_dp)
        logger.info(
            "[MOCK_FINAL] Inserted %s DP at index %d (mock_index=%d, lat=%.6f, lng=%.6f, dist=%.0fm)",
            dp_type, insert_pos, mock_idx, vdp_lat, vdp_lng, mid_dist,
        )
