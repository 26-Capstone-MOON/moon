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
# Mock guidance data — 15 DPs in order
# Pipeline produces 13 DPs. 2 VIRTUAL DPs are inserted at index 1 and 12.
# Each entry: (dp_type, landmark_name, primary, pre_alert, action)
#   dp_type is for reference/logging only; matching is purely by order.
# ---------------------------------------------------------------------------

MOCK_GUIDANCES: list[dict] = [
    # DP0: DEPARTURE (pipeline 1)
    {
        "dp_type": "DEPARTURE",
        "landmark_name": None,
        "primary": "서일체육문화센터에서 출발합니다.",
        "pre_alert": None,
        "action": None,
    },
    # DP1: VIRTUAL — 삽입 (DEPARTURE와 첫 CROSSWALK 사이)
    {
        "dp_type": "VIRTUAL",
        "landmark_name": "서일중학교",
        "primary": "왼쪽에 서일중학교가 있습니다. 횡단보도가 나올 때까지 직진하세요.",
        "pre_alert": None,
        "action": None,
    },
    # DP2: CROSSWALK (pipeline 2)
    {
        "dp_type": "CROSSWALK",
        "landmark_name": "서초초등학교",
        "primary": "서초초등학교 방면으로 횡단보도를 건너세요. 다음 횡단보도가 나올 때까지 직진하세요.",
        "pre_alert": "곧 횡단보도가 나와요.",
        "action": "CROSSWALK",
    },
    # DP3: CROSSWALK (pipeline 3)
    {
        "dp_type": "CROSSWALK",
        "landmark_name": "IBK기업은행 강남역",
        "primary": "IBK기업은행 강남역점 방면으로 횡단보도를 건너세요. 건너서 계속 직진하세요.",
        "pre_alert": "곧 다음 횡단보도가 나와요.",
        "action": "CROSSWALK",
    },
    # DP4: DIRECTION_CHANGE (pipeline 4)
    {
        "dp_type": "DIRECTION_CHANGE",
        "landmark_name": "스파오 강남2호점",
        "primary": "좌회전하면 왼쪽에 스파오 강남2호점이 보여요.",
        "pre_alert": "큰 도로가 보여요. 좌회전을 준비하세요.",
        "action": "LEFT_TURN",
    },
    # DP5: CROSSWALK (pipeline 5)
    {
        "dp_type": "CROSSWALK",
        "landmark_name": "MUJI 강남점",
        "primary": "MUJI 강남점 매장 앞 횡단보도를 건너세요.",
        "pre_alert": "곧 횡단보도가 나와요.",
        "action": "CROSSWALK",
    },
    # DP6: DIRECTION_CHANGE (pipeline 6)
    {
        "dp_type": "DIRECTION_CHANGE",
        "landmark_name": "조앤조의원",
        "primary": "조앤조의원 앞에서 우회전하세요. 강남역 11번 출구까지 계속 직진하세요.",
        "pre_alert": "앞쪽에 조앤조의원이 보여요. 우회전을 준비하세요.",
        "action": "RIGHT_TURN",
    },
    # DP7: DIRECTION_CHANGE (pipeline 7)
    {
        "dp_type": "DIRECTION_CHANGE",
        "landmark_name": "KB국민은행 강남중앙점",
        "primary": "KB국민은행 강남중앙점을 끼고 좌회전하세요. 횡단보도까지 계속 직진하세요.",
        "pre_alert": "강남역 11번 출구 지나면 곧 왼쪽에 국민은행이 보여요. 좌회전을 준비하세요.",
        "action": "LEFT_TURN",
    },
    # DP8: CROSSWALK (pipeline 8)
    {
        "dp_type": "CROSSWALK",
        "landmark_name": "GS25 강남타운점",
        "primary": "GS25 강남타운점 방면으로 횡단보도를 건너세요. 건너서 KB손해보험까지 직진하세요.",
        "pre_alert": "곧 횡단보도가 나와요.",
        "action": "CROSSWALK",
    },
    # DP9: CROSSWALK (pipeline 9)
    {
        "dp_type": "CROSSWALK",
        "landmark_name": "KB손해보험 강남사옥",
        "primary": "KB손해보험 강남사옥 앞에 있는 횡단보도를 건너세요.",
        "pre_alert": "곧 횡단보도가 나와요.",
        "action": "CROSSWALK",
    },
    # DP10: CROSSWALK (pipeline 10)
    {
        "dp_type": "CROSSWALK",
        "landmark_name": None,
        "primary": "왼쪽에 있는 횡단보도를 건너세요. 건너서 계속 직진하세요.",
        "pre_alert": "곧 횡단보도가 나와요.",
        "action": "CROSSWALK",
    },
    # DP11: DIRECTION_CHANGE (pipeline 11)
    {
        "dp_type": "DIRECTION_CHANGE",
        "landmark_name": "우리은행 테헤란로금융센터",
        "primary": "우리은행 테헤란로금융센터에서 우회전하세요. 뚜레쥬르 카페 역삼점까지 계속 직진하세요.",
        "pre_alert": "곧 앞쪽에 우리은행 테헤란로금융센터가 보여요.",
        "action": "RIGHT_TURN",
    },
    # DP12: VIRTUAL — 삽입 (DIRECTION_CHANGE 우회전과 DIRECTION_CHANGE 좌회전 사이)
    {
        "dp_type": "VIRTUAL",
        "landmark_name": "뚜레쥬르 카페역삼점",
        "primary": "왼쪽에 뚜레쥬르 카페 역삼점이 보이면 잘 가고 있는 거예요. 역삼1동주민센터 주차장까지 계속 직진하세요.",
        "pre_alert": None,
        "action": None,
    },
    # DP13: DIRECTION_CHANGE (pipeline 12)
    {
        "dp_type": "DIRECTION_CHANGE",
        "landmark_name": "역삼1동주민센터 공영주차장",
        "primary": "왼쪽에 역삼1동주민센터 공영주차장이 보이면 좌회전하세요.",
        "pre_alert": "곧 왼쪽에 역삼1동주민센터 공영주차장이 보여요. 좌회전을 준비하세요.",
        "action": None,
    },
    # DP14: ARRIVAL (pipeline 13)
    {
        "dp_type": "ARRIVAL",
        "landmark_name": None,
        "primary": "목적지 역삼1동주민센터에 도착했습니다.",
        "pre_alert": None,
        "action": None,
    },
]

# ---------------------------------------------------------------------------
# VIRTUAL DP insertion indices (0-based positions in MOCK_GUIDANCES)
# These are the mock indices that need a VIRTUAL DP inserted into the
# pipeline DP list. Maps mock_index → (before_pipeline_index, after_pipeline_index)
# ---------------------------------------------------------------------------

_VIRTUAL_INSERT_SPECS: list[dict] = [
    # DP1 (VIRTUAL 서일중학교): between pipeline DP0 (DEPARTURE) and DP1 (first CROSSWALK)
    {"mock_index": 1, "before_pipeline": 0, "after_pipeline": 1,
     "fixed_lat": 37.498272, "fixed_lng": 127.022654},
    # DP12 (VIRTUAL 뚜레쥬르): between pipeline DP10 (DIRECTION_CHANGE 우회전) and DP11 (DIRECTION_CHANGE 좌회전)
    {"mock_index": 12, "before_pipeline": 10, "after_pipeline": 11,
     "fixed_lat": 37.497535, "fixed_lng": 127.031905},
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

    Pipeline produces 13 DPs. Mock has 15 entries (13 real + 2 VIRTUAL).
    This function inserts VIRTUAL DPs at index 1 and 12, then overwrites
    all guidance with mock data.

    Returns the (possibly mutated) RouteResponse.
    """
    if not _is_demo_route(origin, dest):
        logger.info("[MOCK] Route does not match demo route — skipping mock guidance")
        return route_response

    dps = route_response.decision_points
    n_pipeline = len(dps)
    n_mock = len(MOCK_GUIDANCES)
    n_virtual = sum(1 for m in MOCK_GUIDANCES if m["dp_type"] == "VIRTUAL")
    n_real_mock = n_mock - n_virtual  # non-VIRTUAL mock entries

    logger.info(
        "[MOCK] Demo route matched! Pipeline DPs=%d, Mock entries=%d (real=%d, virtual=%d)",
        n_pipeline, n_mock, n_real_mock, n_virtual,
    )

    # Expected: pipeline produces n_real_mock DPs, we insert n_virtual to reach n_mock
    if n_pipeline == n_real_mock:
        _insert_virtual_dps(route_response)
        _overwrite_guidance(route_response.decision_points, MOCK_GUIDANCES)
        return route_response

    # Pipeline already has the same count as mock (all VIRTUALs already present)
    if n_pipeline == n_mock:
        _overwrite_guidance(dps, MOCK_GUIDANCES)
        return route_response

    # Fallback: overwrite as many as we can
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


def _insert_virtual_dps(route_response: RouteResponse) -> None:
    """Insert VIRTUAL DPs at predefined positions between pipeline DPs.

    Inserts are done in reverse order (highest index first) so that earlier
    indices remain valid after each insertion.

    Coordinates: midpoint of surrounding DPs, unless fixed_lat/fixed_lng specified.
    distance_from_start: always interpolated from surrounding DPs.
    """
    dps = route_response.decision_points

    # Sort specs by before_pipeline descending so insertions don't shift indices
    specs = sorted(_VIRTUAL_INSERT_SPECS, key=lambda s: s["before_pipeline"], reverse=True)

    for spec in specs:
        before_idx = spec["before_pipeline"]
        after_idx = spec["after_pipeline"]
        mock_idx = spec["mock_index"]

        if before_idx >= len(dps) or after_idx >= len(dps):
            logger.warning(
                "[MOCK] Cannot insert VIRTUAL at mock_index=%d: "
                "pipeline has only %d DPs (need indices %d and %d)",
                mock_idx, len(dps), before_idx, after_idx,
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

        virtual_dp = DecisionPoint(
            dp_id=f"dp-virtual-mock-{uuid.uuid4().hex[:6]}",
            dp_type="VIRTUAL",
            turn_type=None,
            location=Location(latitude=vdp_lat, longitude=vdp_lng),
            distance_from_start=mid_dist,
            guidance=Guidance(primary="", pre_alert=None, action=None),
        )

        insert_pos = after_idx  # insert before the "after" DP
        dps.insert(insert_pos, virtual_dp)
        logger.info(
            "[MOCK] Inserted VIRTUAL DP at index %d (mock_index=%d, lat=%.6f, lng=%.6f, dist=%.0fm)",
            insert_pos, mock_idx, vdp_lat, vdp_lng, mid_dist,
        )
