"""
재라우팅 시연용 mock_guidance.

시연 시나리오:
- 원본 경로: 버거킹 신논현 → 스타벅스 강남에비뉴 (mock_guidance_final.py)
- 의도적 이탈 발동 영역(zone): 중심 (37.5038819, 127.0236635), 반경 50m
- 이 zone 안에서 재라우팅의 새 origin이 잡히면 mock 발동
- destination은 mock_guidance_final.py와 동일한 스타벅스 강남에비뉴점

매칭 조건 (AND):
1. 새 경로의 origin이 이탈 zone 안에 있음 (반경 50m)
2. 새 경로의 destination이 시연 목적지(DEMO_ROUTE_DEST) 근처 (mock_guidance_final.py와 동일 임계값 100m)

Lockito 시뮬레이션과 실제 디바이스 GPS의 흔들림을 흡수하기 위해
이탈 zone 반경을 50m로 두었다. previous_route_id는 매칭에 사용하지 않으므로
route_id 재발급이나 외부 curl 단독 테스트에도 견고하다.
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
from mock_guidance_final import (
    DEMO_ROUTE_DEST,
    _MATCH_THRESHOLD_M,
)

logger = logging.getLogger(__name__)

# === 매칭 상수: 이탈 발동 zone ===
# Lockito GPX 분석 결과 기준 이탈 구간(약 27m 직선)의 중간 지점.
# GPS 흔들림 + Lockito 시뮬레이션 오차 흡수 마진 포함.
REROUTE_ZONE_CENTER_LAT = 37.5038819
REROUTE_ZONE_CENTER_LNG = 127.0236635
REROUTE_ZONE_RADIUS_M = 50.0

# Tmap이 reroute에 대해 줄 것으로 예상되는 pipeline DP 개수
# (DEPARTURE + DIRECTION_CHANGE(공차?) + ARRIVAL = 3)
# 이 값과 일치할 때만 _insert_extra_dps_reroute로 VIRTUAL CU를 강제 삽입.
_EXPECTED_REROUTE_PIPELINE_DP_COUNT = 3

# === Mock 데이터 ===
# 비어있는 상태로 시작. Phase 3 이후 별도 작업으로
# 실제 새 경로 DP 구성에 맞춰 채울 것.
# 스키마는 mock_guidance_final.py의 MOCK_GUIDANCES와 동일.
REROUTE_MOCK_GUIDANCES: list[dict] = [
    # DP0 — DEPARTURE (이탈 zone에서 출발, CU까지 직진)
    {
        "dp_type": "DEPARTURE",
        "landmark_name": "투썸플레이스 교보타워사거리점",
        "landmark_lat": 37.503756,
        "landmark_lng": 127.023631,
        "dp_marker_lat": 37.503761,
        "dp_marker_lng": 127.023710,
        "pan_override": 162.94,
        "primary": "현재 위치에서 출발합니다. \n이마트24를 오른쪽에 두고 편의점 CU까지 직진하세요.",
        "pre_alert": None,
        "action": None,
        "appearance": None,
    },
    # DP1 — CU 서초유앤아이점 (VIRTUAL, 직진 확인)
    {
        "dp_type": "VIRTUAL",
        "landmark_name": "CU 서초유앤아이점",
        "landmark_lat": 37.503197,
        "landmark_lng": 127.023735,
        "dp_marker_lat": 37.503306,
        "dp_marker_lng": 127.023886,
        "pan_override": None,
        "primary": "CU를 오른쪽에 두고 카페 공차까지 직진하세요.",
        "pre_alert": None,
        "action": None,
        "appearance": "보라색 간판에 'Nice to CU'가 쓰여져 있는 편의점입니다.",
    },
    # DP2 — 공차 교보타워점 (DIRECTION_CHANGE, 우회전)
    {
        "dp_type": "DIRECTION_CHANGE",
        "landmark_name": "공차 교보타워점",
        "landmark_lat": 37.502569,
        "landmark_lng": 127.024151,
        "dp_marker_lat": 37.502568,
        "dp_marker_lng": 127.024216,
        "pan_override": None,
        "primary": "공차 앞 계단을 따라 내려간 뒤 우회전하세요. \n우회전 후 스타벅스까지 직진입니다.",
        "pre_alert": "곧 오른쪽에 카페 공차가 보여요. 우회전을 준비하세요.",
        "action": "RIGHT_TURN",
        "appearance": "회색 대리석 간판에 흰색 글씨로 'Gong Cha'가 쓰여져 있는 카페입니다.",
    },
    # DP3 — 스타벅스 강남에비뉴점 (ARRIVAL, 도착)
    {
        "dp_type": "ARRIVAL",
        "landmark_name": "스타벅스 강남에비뉴점",
        "landmark_lat": 37.502550,
        "landmark_lng": 127.024091,
        "dp_marker_lat": 37.502478,
        "dp_marker_lng": 127.024073,
        "pan_override": None,
        "primary": "목적지 스타벅스 강남에비뉴점에 도착했습니다. \n안내를 종료합니다.",
        "pre_alert": None,
        "action": None,
        "appearance": "초록색 스타벅스 로고와 흰색 글씨로 'STARBUCKS'가 쓰여져 있는 카페입니다. 통유리로 된 건물 1층에 있습니다.",
    },
]

# ---------------------------------------------------------------------------
# Extra DP insertion specs.
# Tmap이 reroute에 대해 만들어주지 않는 VIRTUAL CU DP를 강제 삽입.
# mock_guidance_final.py의 _EXTRA_INSERT_SPECS와 동일한 스키마.
# ---------------------------------------------------------------------------

_REROUTE_EXTRA_INSERT_SPECS: list[dict] = [
    # CU 서초유앤아이점 VIRTUAL — pipeline DP0(DEPARTURE)와 DP1(공차/ARRIVAL) 사이에 삽입
    {
        "mock_index": 1,
        "dp_type": "VIRTUAL",
        "before_pipeline": 0,
        "after_pipeline": 1,
        "fixed_lat": 37.503306,
        "fixed_lng": 127.023886,
    },
]


def _is_reroute_demo(origin: Location, dest: Location) -> bool:
    """새 경로가 재라우팅 시연 시나리오에 해당하는지 판정.

    조건 (AND):
    1. origin이 이탈 zone(반경 50m) 안에 있음
    2. dest가 DEMO_ROUTE_DEST(반경 100m) 근처
    """
    origin_dist = haversine(
        origin.latitude, origin.longitude,
        REROUTE_ZONE_CENTER_LAT, REROUTE_ZONE_CENTER_LNG,
    )
    if origin_dist > REROUTE_ZONE_RADIUS_M:
        return False

    dest_dist = haversine(
        dest.latitude, dest.longitude,
        DEMO_ROUTE_DEST[0], DEMO_ROUTE_DEST[1],
    )
    if dest_dist > _MATCH_THRESHOLD_M:
        return False

    return True


def apply_mock_guidance(
    route_response: RouteResponse,
    origin: Location,
    dest: Location,
) -> RouteResponse:
    """재라우팅 결과에 시연용 mock 안내문을 적용한다.

    mock_guidance_final.apply_mock_guidance와 동일한 호출 패턴:
    - 매칭 실패 시 INFO 로그 + route_response 그대로 반환
    - 매칭 성공 시 in-place로 dp.guidance / selected_landmark / location 등 덮어씀
    """
    # 1. 빈 데이터 가드 (early return)
    if not REROUTE_MOCK_GUIDANCES:
        logger.info(
            "[MOCK_REROUTE] REROUTE_MOCK_GUIDANCES is empty — skipping (골격 상태)"
        )
        return route_response

    # 2. zone + destination 매칭
    if not _is_reroute_demo(origin, dest):
        origin_dist = haversine(
            origin.latitude, origin.longitude,
            REROUTE_ZONE_CENTER_LAT, REROUTE_ZONE_CENTER_LNG,
        )
        logger.info(
            "[MOCK_REROUTE] Route does not match reroute zone "
            "(origin_dist=%.1fm, zone_radius=%.1fm) — skipping mock guidance",
            origin_dist, REROUTE_ZONE_RADIUS_M,
        )
        return route_response

    # 3. 매칭 성공 → DP 개수에 따라 분기
    dps = route_response.decision_points
    n_pipeline = len(dps)
    n_mock = len(REROUTE_MOCK_GUIDANCES)
    n_extra = len(_REROUTE_EXTRA_INSERT_SPECS)

    logger.info(
        "[MOCK_REROUTE] Reroute demo matched! Pipeline DPs=%d, Mock entries=%d "
        "(expected_pipeline=%d, extra=%d)",
        n_pipeline, n_mock, _EXPECTED_REROUTE_PIPELINE_DP_COUNT, n_extra,
    )

    if n_pipeline == _EXPECTED_REROUTE_PIPELINE_DP_COUNT:
        # 예상대로 3개 → VIRTUAL CU 강제 삽입해서 4개로 정렬
        logger.info(
            "[MOCK_REROUTE] Pipeline DPs=%d matches expected — inserting %d extra DP(s)",
            n_pipeline, n_extra,
        )
        _insert_extra_dps_reroute(route_response)
    elif n_pipeline == n_mock:
        # 이미 mock 개수와 일치 → 삽입 skip
        logger.info(
            "[MOCK_REROUTE] Pipeline DPs=%d already matches mock count — skipping insert",
            n_pipeline,
        )
    else:
        # 예상치 못한 개수 → fallback (가능한 만큼만 매핑)
        logger.warning(
            "[MOCK_REROUTE] Unexpected DP count (pipeline=%d, mock=%d) "
            "— overwriting first %d DPs only, rest keep original guidance",
            n_pipeline, n_mock, min(n_pipeline, n_mock),
        )

    # 4. 인덱스 정렬 완료 → 1:1 덮어쓰기
    _overwrite_guidance(route_response.decision_points, REROUTE_MOCK_GUIDANCES)

    return route_response


def _overwrite_guidance(
    dps: list[DecisionPoint],
    mocks: list[dict],
) -> None:
    """mock_guidance_final._overwrite_guidance와 동일한 패턴으로 dp 덮어쓰기.

    1:1 인덱스 매핑. mock 수 > dp 수면 남는 mock 무시.
    """
    for i, mock in enumerate(mocks):
        if i >= len(dps):
            break

        # dp_type 덮어쓰기 (mock에 dp_type이 있고 현재와 다를 때만)
        mock_dp_type = mock.get("dp_type")
        if mock_dp_type and dps[i].dp_type != mock_dp_type:
            logger.info(
                "[MOCK_REROUTE] DP%d dp_type %s → %s (overwritten by mock)",
                i, dps[i].dp_type, mock_dp_type,
            )
            dps[i].dp_type = mock_dp_type
            dps[i].turn_type = None

        # guidance 새 객체로 통째 교체
        dps[i].guidance = Guidance(
            primary=mock["primary"],
            pre_alert=mock.get("pre_alert"),
            action=mock.get("action"),
        )

        # selected_landmark 재구성 (landmark_name이 있을 때만)
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

        # dp.location 덮어쓰기 (dp_marker_lat/lng 둘 다 not None일 때만)
        marker_lat = mock.get("dp_marker_lat")
        marker_lng = mock.get("dp_marker_lng")
        if marker_lat is not None and marker_lng is not None:
            dps[i].location = Location(latitude=marker_lat, longitude=marker_lng)
            if dps[i].panorama_request is not None:
                dps[i].panorama_request.location = Location(
                    latitude=marker_lat, longitude=marker_lng
                )
            logger.info(
                "[MOCK_REROUTE] DP%d marker/panorama location overridden to (%.6f, %.6f)",
                i, marker_lat, marker_lng,
            )

        # pan_override 적용 (not None이고 panorama_request도 있을 때)
        pan_val = mock.get("pan_override")
        if pan_val is not None and dps[i].panorama_request is not None:
            dps[i].panorama_request.pan_override = pan_val

        # 요약 로그 (mock_guidance_final.py 패턴 그대로)
        logger.info(
            "[MOCK_REROUTE] DP%d (%s) landmark=%s pan_override=%s → %s",
            i, dps[i].dp_type, lm_name or "null",
            pan_val if pan_val is not None else "none",
            mock["primary"][:40],
        )


def _insert_extra_dps_reroute(route_response: RouteResponse) -> None:
    """Insert extra DPs (any dp_type) at predefined positions between pipeline DPs.

    mock_guidance_final._insert_extra_dps와 동일 패턴 (prefix만 [MOCK_REROUTE]).

    Inserts are done in reverse order (highest before_pipeline first) so that
    earlier indices remain valid after each insertion.

    Coordinates: midpoint of surrounding DPs, unless fixed_lat/fixed_lng specified.
    distance_from_start: always interpolated from surrounding DPs.
    dp_type: taken from spec["dp_type"] (not hardcoded).
    """
    dps = route_response.decision_points

    # Sort specs by before_pipeline descending so insertions don't shift indices
    specs = sorted(
        _REROUTE_EXTRA_INSERT_SPECS,
        key=lambda s: (s["before_pipeline"], s["mock_index"]),
        reverse=True,
    )

    for spec in specs:
        before_idx = spec["before_pipeline"]
        after_idx = spec["after_pipeline"]
        mock_idx = spec["mock_index"]
        dp_type = spec["dp_type"]

        if before_idx >= len(dps) or after_idx >= len(dps):
            logger.warning(
                "[MOCK_REROUTE] Cannot insert %s at mock_index=%d: "
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
            "[MOCK_REROUTE] Inserted %s DP at index %d (mock_index=%d, lat=%.6f, lng=%.6f, dist=%.0fm)",
            dp_type, insert_pos, mock_idx, vdp_lat, vdp_lng, mid_dist,
        )
