"""Mock guidance for demo route (서일문화센터 → 역삼1동주민센터).

When MOCK_GUIDANCE=True, pipeline-generated guidance is replaced with
hand-crafted Korean text. Only the guidance field is overwritten — coordinates,
distance, landmarks, panorama data all remain from the real pipeline.
"""

from __future__ import annotations

import logging
import uuid

from geo import haversine
from schemas import (
    DecisionPoint,
    Guidance,
    Location,
    RouteResponse,
    SelectedLandmark,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Demo route coordinates
# ---------------------------------------------------------------------------

DEMO_ROUTE_ORIGIN = (37.4981, 127.0222)   # 서일문화센터
DEMO_ROUTE_DEST   = (37.4955, 127.0331)   # 역삼1동주민센터

_MATCH_THRESHOLD_M = 100.0  # origin/dest must be within 100m to apply mock

# ---------------------------------------------------------------------------
# Mock guidance data — 14 DPs in order
# Each entry: (dp_type, primary, pre_alert, action)
#   dp_type is for reference/logging only; matching is purely by order.
# ---------------------------------------------------------------------------

MOCK_GUIDANCES: list[dict] = [
    # DP0: DEPARTURE
    {
        "dp_type": "DEPARTURE",
        "landmark_name": None,
        "primary": "서일체육문화센터에서 출발합니다. 왼쪽에 학교 운동장 울타리가 보여요. 울타리를 따라 쭉 직진하세요.",
        "pre_alert": None,
        "action": None,
    },
    # DP1: CROSSWALK
    {
        "dp_type": "CROSSWALK",
        "landmark_name": "장꼬방",
        "primary": "사거리 횡단보도를 건너세요. 오른쪽에 빨간 벽돌 건물 장꼬방이 보여요. 서초초등학교 방향으로 직진하세요.",
        "pre_alert": "전방에 사거리 횡단보도가 있어요. 오른쪽에 장꼬방 빨간 건물이 보여요.",
        "action": "CROSSWALK",
    },
    # DP2: CROSSWALK
    {
        "dp_type": "CROSSWALK",
        "landmark_name": "IBK기업은행 강남역점",
        "primary": "IBK기업은행 강남역점 앞 횡단보도를 건너세요. 건너면 오른쪽에 벽화가 그려진 담장이 보여요. 그 방향으로 직진하세요.",
        "pre_alert": "전방에 횡단보도가 있어요. 왼쪽에 IBK기업은행이 보여요.",
        "action": "CROSSWALK",
    },
    # DP3: DIRECTION_CHANGE (left turn)
    {
        "dp_type": "DIRECTION_CHANGE",
        "landmark_name": "SPAO",
        "primary": "오른쪽에 SPAO 매장이 보이면 좌회전하세요. 큰 도로가 나와요.",
        "pre_alert": "조금 있으면 오른쪽에 SPAO 간판이 보여요. 좌회전 준비하세요.",
        "action": "LEFT_TURN",
    },
    # DP4: CROSSWALK
    {
        "dp_type": "CROSSWALK",
        "landmark_name": "MUJI",
        "primary": "MUJI 매장 앞 횡단보도를 건너세요. 왼쪽에 파고다타워가 보여요.",
        "pre_alert": "전방에 횡단보도가 있어요. 왼쪽에 MUJI 빨간 간판이 보여요.",
        "action": "CROSSWALK",
    },
    # DP5: DIRECTION_CHANGE (right turn)
    {
        "dp_type": "DIRECTION_CHANGE",
        "landmark_name": "조앤조의원",
        "primary": "조앤조의원 앞 횡단보도를 건너세요. 건너서 쭉 직진하세요.",
        "pre_alert": "전방에 횡단보도가 있어요. 왼쪽에 조앤조의원 파란 간판이 보여요.",
        "action": "RIGHT_TURN",
    },
    # DP6: DIRECTION_CHANGE (left turn)
    {
        "dp_type": "DIRECTION_CHANGE",
        "landmark_name": "KB국민은행 강남중앙점",
        "primary": "강남역 11번 출구 옆 KB국민은행 강남중앙점에서 좌회전하세요.",
        "pre_alert": "조금 있으면 왼쪽에 KB국민은행이 보여요. 좌회전 준비하세요.",
        "action": "LEFT_TURN",
    },
    # DP7: CROSSWALK
    {
        "dp_type": "CROSSWALK",
        "landmark_name": "GS25 강남타운점",
        "primary": "GS25 강남타운점 앞 횡단보도를 건너세요. 건너면 오른쪽에 공차 빨간 간판이 보여요. 그 방향으로 직진하세요.",
        "pre_alert": "전방에 횡단보도가 있어요. 오른쪽에 GS25 파란 간판이 보여요.",
        "action": "CROSSWALK",
    },
    # DP8: CROSSWALK
    {
        "dp_type": "CROSSWALK",
        "landmark_name": "KB손해보험 강남사옥",
        "primary": "국기원입구 사거리 횡단보도를 건너세요. 왼쪽에 KB손해보험 강남사옥 유리 건물이 보여요.",
        "pre_alert": "전방에 국기원입구 사거리가 있어요. 횡단보도를 건널 준비하세요.",
        "action": "CROSSWALK",
    },
    # DP9: CROSSWALK
    {
        "dp_type": "CROSSWALK",
        "landmark_name": "KT플라자",
        "primary": "횡단보도를 건너세요. 오른쪽에 KT플라자 건물이 보여요. 그 방향으로 직진하세요.",
        "pre_alert": "전방에 횡단보도가 있어요. 오른쪽에 KT플라자가 보여요.",
        "action": "CROSSWALK",
    },
    # DP10: DIRECTION_CHANGE (right turn)
    {
        "dp_type": "DIRECTION_CHANGE",
        "landmark_name": "우리은행 삼원아케이드",
        "primary": "오른쪽에 우리은행 간판과 삼원아케이드 아치형 입구가 보이면 우회전하세요.",
        "pre_alert": "조금 있으면 오른쪽에 우리은행 파란 간판이 보여요. 우회전 준비하세요.",
        "action": "RIGHT_TURN",
    },
    # DP11: VIRTUAL (confirmation — inserted between pipeline DP10 and DP11)
    {
        "dp_type": "VIRTUAL",
        "landmark_name": "뚜레쥬르",
        "primary": "왼쪽에 뚜레쥬르가 보이면 잘 가고 있는 거예요. 계속 직진하세요.",
        "pre_alert": None,
        "action": None,
    },
    # DP12: DIRECTION_CHANGE (left turn)
    {
        "dp_type": "DIRECTION_CHANGE",
        "landmark_name": "역삼1동주민센터",
        "primary": "왼쪽에 역삼1동주민센터 유리 건물이 보이면 좌회전하세요.",
        "pre_alert": "뚜레쥬르 지나면 곧 왼쪽에 역삼1동주민센터가 보여요. 좌회전 준비하세요.",
        "action": "LEFT_TURN",
    },
    # DP13: ARRIVAL
    {
        "dp_type": "ARRIVAL",
        "landmark_name": None,
        "primary": "목적지 역삼1동주민센터에 도착했습니다.",
        "pre_alert": None,
        "action": None,
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

    Only the ``guidance`` field of each DP is replaced. Coordinates,
    distance_from_start, selected_landmark, panorama_request, etc. are
    preserved from the real pipeline.

    Returns the (possibly mutated) RouteResponse.
    """
    if not _is_demo_route(origin, dest):
        logger.info("[MOCK] Route does not match demo route — skipping mock guidance")
        return route_response

    dps = route_response.decision_points
    n_pipeline = len(dps)
    n_mock = len(MOCK_GUIDANCES)

    logger.info(
        "[MOCK] Demo route matched! Pipeline DPs=%d, Mock entries=%d",
        n_pipeline, n_mock,
    )

    # Simple case: same count → 1:1 overwrite
    if n_pipeline == n_mock:
        _overwrite_guidance(dps, MOCK_GUIDANCES)
        return route_response

    # Pipeline produced fewer DPs than mock entries → try inserting virtual DP
    if n_pipeline == n_mock - 1:
        _insert_virtual_dp(route_response)
        _overwrite_guidance(route_response.decision_points, MOCK_GUIDANCES)
        return route_response

    # Fallback: overwrite as many as we can (min of both)
    count = min(n_pipeline, n_mock)
    logger.warning(
        "[MOCK] DP count mismatch (pipeline=%d, mock=%d). "
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
        dps[i].guidance = Guidance(
            primary=mock["primary"],
            pre_alert=mock.get("pre_alert"),
            action=mock.get("action"),
        )
        lm_name = mock.get("landmark_name")
        if lm_name:
            dps[i].selected_landmark = SelectedLandmark(
                name=lm_name,
                category_code="MOCK",
                position="FRONT",
                distance=0.0,
                score=1.0,
                match_status="POI_ONLY",
                is_open=True,
            )
        else:
            dps[i].selected_landmark = None
        logger.info(
            "[MOCK] DP%d (%s) landmark=%s → %s",
            i, dps[i].dp_type, lm_name or "null", mock["primary"][:40],
        )


def _insert_virtual_dp(route_response: RouteResponse) -> None:
    """Insert a VIRTUAL DP between the 11th and 12th pipeline DP.

    The virtual DP location is the midpoint between DP[10] and DP[11]
    on the route LineString.
    """
    dps = route_response.decision_points
    if len(dps) < 12:
        logger.warning("[MOCK] Not enough DPs to insert virtual DP")
        return

    dp_before = dps[10]  # pipeline DP10 (0-indexed)
    dp_after = dps[11]   # pipeline DP11

    # Midpoint between the two DPs
    mid_lat = (dp_before.location.latitude + dp_after.location.latitude) / 2
    mid_lng = (dp_before.location.longitude + dp_after.location.longitude) / 2
    mid_dist = (dp_before.distance_from_start + dp_after.distance_from_start) / 2

    virtual_dp = DecisionPoint(
        dp_id=f"dp-virtual-mock-{uuid.uuid4().hex[:6]}",
        dp_type="VIRTUAL",
        turn_type=None,
        location=Location(latitude=mid_lat, longitude=mid_lng),
        distance_from_start=mid_dist,
        guidance=Guidance(primary="", pre_alert=None, action=None),  # overwritten later
    )

    dps.insert(11, virtual_dp)
    logger.info(
        "[MOCK] Inserted VIRTUAL DP at index 11 (lat=%.4f, lng=%.4f, dist=%.0fm)",
        mid_lat, mid_lng, mid_dist,
    )
