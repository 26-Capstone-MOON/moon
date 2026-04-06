"""STEP 6: Guidance generator — Korean guidance text per DP.

Generates Guidance (primary + pre_alert + action) based on DP type,
selected landmark, match_status, Vision environment descriptions,
and facility visibility.
"""

from __future__ import annotations

from dataclasses import dataclass

from constants import (
    FACILITY_KOREAN_NAMES,
    FACILITY_TURN_TYPES,
    TURN_TYPE_TO_ACTION,
)
from schemas import DecisionPoint, Guidance
from scoring_service import ScoredPoi

# ---------------------------------------------------------------------------
# Position text mapping
# ---------------------------------------------------------------------------

POSITION_TEXT: dict[str, str] = {
    "LEFT": "왼쪽에",
    "RIGHT": "오른쪽에",
    "FRONT": "전방에",
}

# ---------------------------------------------------------------------------
# Action text mapping (GuidanceAction → Korean)
# ---------------------------------------------------------------------------

ACTION_TEXT: dict[str, str] = {
    "LEFT_TURN": "좌회전",
    "RIGHT_TURN": "우회전",
    "U_TURN": "유턴",
    "CROSSWALK": "횡단보도",
    "STAIRS_UP": "올라가세요",
    "STAIRS_DOWN": "내려가세요",
    "OVERPASS": "건너세요",
    "UNDERPASS": "내려가세요",
    "ELEVATOR": "이용하세요",
}

# ---------------------------------------------------------------------------
# Facility action text (turnType → full sentence)
# ---------------------------------------------------------------------------

FACILITY_ACTION_TEXT: dict[int, str] = {
    125: "육교를 건너세요.",
    126: "지하보도로 내려가세요.",
    127: "계단으로 올라가세요.",
    128: "계단으로 내려가세요.",
    129: "계단으로 올라가세요.",
    218: "엘리베이터를 이용하세요.",
}

# ---------------------------------------------------------------------------
# Korean particle helper (조사 처리)
# ---------------------------------------------------------------------------


def _has_batchim(char: str) -> bool:
    """Check if a Korean character has a final consonant (받침).

    Args:
        char: single character to check.

    Returns:
        True if the character has batchim, False otherwise.
        Non-Korean characters are treated as no batchim.
    """
    if not ("가" <= char <= "힣"):
        return False
    return (ord(char) - 0xAC00) % 28 != 0


def _particle(name: str, with_batchim: str, without_batchim: str) -> str:
    """Append the correct Korean particle to a name.

    Args:
        name: the noun to attach the particle to.
        with_batchim: particle form when last char has batchim.
        without_batchim: particle form when last char has no batchim.

    Returns:
        name + appropriate particle.
    """
    if not name:
        return name
    last_char = name.rstrip()[-1]
    particle = with_batchim if _has_batchim(last_char) else without_batchim
    return f"{name}{particle}"


# ---------------------------------------------------------------------------
# GuidanceInput dataclass
# ---------------------------------------------------------------------------


@dataclass
class GuidanceInput:
    """All context needed to generate guidance for a single DP."""

    dp_index: int
    dp_type: str
    turn_type: int | None
    action: str | None
    distance_from_start: float
    selected_landmark: ScoredPoi | None
    match_status: str | None
    environment_desc: str | None
    facility_visible: bool | None
    prev_landmark_name: str | None
    next_dp_distance: float | None


# ---------------------------------------------------------------------------
# Internal text builders
# ---------------------------------------------------------------------------


def _get_action_text(action: str | None) -> str:
    """Convert GuidanceAction to Korean verb form.

    Args:
        action: GuidanceAction enum value.

    Returns:
        Korean action text, defaults to "직진".
    """
    if action is None:
        return "직진"
    return ACTION_TEXT.get(action, "직진")


def _landmark_with_env(
    landmark: ScoredPoi | None,
    match_status: str | None,
    environment_desc: str | None,
    distance_from_start: float = 0.0,
    next_dp_distance: float | None = None,
) -> str:
    """Build landmark reference text based on match_status.

    Args:
        landmark: selected landmark (may be None).
        match_status: MATCHED / POI_ONLY / VISION_ONLY / None.
        environment_desc: Vision environment description.
        distance_from_start: for distance fallback.
        next_dp_distance: distance to next DP (for fallback text).

    Returns:
        Landmark reference string for embedding in guidance templates.
    """
    if landmark is None or match_status is None:
        if next_dp_distance is not None:
            return f"{int(next_dp_distance)}m 앞"
        return f"{int(distance_from_start)}m 앞"

    name = landmark.poi.place_name

    if match_status == "MATCHED":
        return name
    elif match_status == "POI_ONLY":
        if environment_desc:
            return f"{environment_desc} {name}"
        return name
    elif match_status == "VISION_ONLY":
        if environment_desc:
            return environment_desc
        return name
    return name


def _position_text(landmark: ScoredPoi | None) -> str:
    """Get position text for a landmark.

    Args:
        landmark: selected landmark.

    Returns:
        Korean position text (e.g., "왼쪽에").
    """
    if landmark is None:
        return "전방에"
    return POSITION_TEXT.get(landmark.poi.position, "전방에")


# ---------------------------------------------------------------------------
# Per-type guidance generators
# ---------------------------------------------------------------------------


def _generate_departure(
    turn_type: int | None,
    action: str | None,
    **kwargs,
) -> Guidance:
    """Generate DEPARTURE guidance.

    Args:
        turn_type: Tmap turnType.
        action: next DP's action (not this DP's).

    Returns:
        Guidance with fixed departure text.
    """
    action_text = _get_action_text(action)
    primary = f"안내를 시작합니다. {action_text}하세요."
    return Guidance(primary=primary, pre_alert=None, action=None)


def _generate_arrival(
    dest_name: str = "",
    **kwargs,
) -> Guidance:
    """Generate ARRIVAL guidance.

    Args:
        dest_name: destination name.

    Returns:
        Guidance with arrival text.
    """
    if dest_name:
        primary = f"목적지 {dest_name}에 도착했습니다."
    else:
        primary = "목적지에 도착했습니다."
    return Guidance(primary=primary, pre_alert=None, action=None)


def _generate_direction_change(
    turn_type: int | None,
    action: str | None,
    landmark: ScoredPoi | None,
    match_status: str | None,
    environment_desc: str | None,
    prev_landmark_name: str | None,
    distance_from_start: float,
    next_dp_distance: float | None,
) -> Guidance:
    """Generate DIRECTION_CHANGE guidance (3-step pattern).

    Args:
        turn_type: Tmap turnType.
        action: GuidanceAction enum value.
        landmark: selected landmark.
        match_status: cross-validation result.
        environment_desc: Vision environment description.
        prev_landmark_name: previous DP's landmark name.
        distance_from_start: distance from route start.
        next_dp_distance: distance to next DP.

    Returns:
        Guidance with primary and pre_alert.
    """
    action_text = _get_action_text(action)
    lm_text = _landmark_with_env(
        landmark, match_status, environment_desc,
        distance_from_start, next_dp_distance,
    )

    # primary
    if landmark is not None and match_status is not None:
        primary = f"{lm_text}에서 {action_text}하세요."
    else:
        primary = f"여기서 {action_text}하세요."

    # pre_alert
    if landmark is not None and match_status is not None:
        lm_with_particle = _particle(lm_text, "이", "가")
        if prev_landmark_name:
            pre_alert = f"{prev_landmark_name} 지나면 곧 {lm_with_particle} 보여요."
        else:
            pre_alert = (
                f"조금 있으면 {lm_with_particle} 보여요. {action_text} 준비하세요."
            )
    else:
        if next_dp_distance is not None:
            pre_alert = f"{int(next_dp_distance)}m 앞에서 {action_text} 준비하세요."
        else:
            pre_alert = f"{action_text} 준비하세요."

    return Guidance(primary=primary, pre_alert=pre_alert, action=action)


def _generate_crosswalk(
    turn_type: int | None,
    action: str | None,
    landmark: ScoredPoi | None,
    match_status: str | None,
    environment_desc: str | None,
    facility_visible: bool | None,
    distance_from_start: float,
    next_dp_distance: float | None,
    after_landmark: ScoredPoi | None = None,
    after_match_status: str | None = None,
    after_environment_desc: str | None = None,
) -> Guidance:
    """Generate CROSSWALK guidance (before + after crossing).

    Args:
        turn_type: Tmap turnType.
        action: GuidanceAction enum value.
        landmark: before-crossing landmark.
        match_status: before-crossing match_status.
        environment_desc: before-crossing environment desc.
        facility_visible: whether crosswalk is visible.
        distance_from_start: distance from route start.
        next_dp_distance: distance to next DP.
        after_landmark: after-crossing landmark.
        after_match_status: after-crossing match_status.
        after_environment_desc: after-crossing environment desc.

    Returns:
        Guidance with primary and pre_alert.
    """
    # facility visibility fallback
    if facility_visible is False:
        dist = int(next_dp_distance) if next_dp_distance else int(distance_from_start)
        primary = f"{dist}m 앞에서 횡단보도를 건너세요."
        pre_alert = f"{dist}m 앞에 횡단보도가 있어요."
        return Guidance(primary=primary, pre_alert=pre_alert, action=action)

    # before-crossing text for pre_alert
    before_text = _landmark_with_env(
        landmark, match_status, environment_desc,
        distance_from_start, next_dp_distance,
    )

    if landmark is not None and match_status is not None:
        pre_alert = f"{before_text} 앞 횡단보도가 있어요."
    else:
        pre_alert = "전방에 횡단보도가 있어요."

    # after-crossing text for primary
    after_text = _landmark_with_env(
        after_landmark, after_match_status, after_environment_desc,
        distance_from_start, next_dp_distance,
    )

    if after_landmark is not None and after_match_status is not None:
        primary = f"횡단보도를 건너 {after_text} 방향으로 직진하세요."
    else:
        primary = "횡단보도를 건너 직진하세요."

    return Guidance(primary=primary, pre_alert=pre_alert, action=action)


def _generate_vertical_move(
    turn_type: int | None,
    action: str | None,
    landmark: ScoredPoi | None,
    match_status: str | None,
    environment_desc: str | None,
    facility_visible: bool | None,
    distance_from_start: float,
    next_dp_distance: float | None,
) -> Guidance:
    """Generate VERTICAL_MOVE guidance (fixed facility + POI assist).

    Args:
        turn_type: Tmap turnType.
        action: GuidanceAction enum value.
        landmark: selected landmark (location assist role).
        match_status: cross-validation result.
        environment_desc: Vision environment description.
        facility_visible: whether facility is visible.
        distance_from_start: distance from route start.
        next_dp_distance: distance to next DP.

    Returns:
        Guidance with primary text.
    """
    facility_action = FACILITY_ACTION_TEXT.get(turn_type or 0, "직진하세요.")
    facility_type = FACILITY_TURN_TYPES.get(turn_type or 0, "")
    facility_korean = FACILITY_KOREAN_NAMES.get(facility_type, "시설물")

    # facility not visible → distance fallback
    if facility_visible is False:
        dist = int(next_dp_distance) if next_dp_distance else int(distance_from_start)
        facility_with_particle = _particle(facility_korean, "이", "가")
        primary = f"{dist}m 앞에 {facility_with_particle} 있어요. {facility_action}"
        return Guidance(primary=primary, pre_alert=None, action=action)

    # poi_location_text based on match_status
    if landmark is not None and match_status is not None:
        pos_text = _position_text(landmark)
        name = landmark.poi.place_name

        if match_status == "MATCHED":
            poi_loc = f"{pos_text} {name} 지나면 바로"
        elif match_status == "POI_ONLY":
            if environment_desc:
                poi_loc = f"{pos_text} {environment_desc} {name} 지나면 바로"
            else:
                poi_loc = f"{pos_text} {name} 지나면 바로"
        elif match_status == "VISION_ONLY":
            if environment_desc:
                poi_loc = f"{environment_desc} 끝나는 지점에"
            else:
                poi_loc = "전방에"
        else:
            poi_loc = "전방에"
    else:
        poi_loc = "전방에"

    # When no POI and no env, add facility name for clarity
    if poi_loc == "전방에" and landmark is None:
        facility_with_particle = _particle(facility_korean, "이", "가")
        primary = f"전방에 {facility_with_particle} 있어요. {facility_action}"
    else:
        primary = f"{poi_loc} {facility_action}"

    return Guidance(primary=primary, pre_alert=None, action=action)


def _generate_virtual(
    landmark: ScoredPoi | None,
    match_status: str | None,
    environment_desc: str | None,
    distance_from_start: float,
    next_dp_distance: float | None,
) -> Guidance:
    """Generate VIRTUAL (midpoint confirmation) guidance.

    Args:
        landmark: selected landmark.
        match_status: cross-validation result.
        environment_desc: Vision environment description.
        distance_from_start: distance from route start.
        next_dp_distance: distance to next DP.

    Returns:
        Guidance with confirmation text.
    """
    if landmark is None or match_status is None:
        return Guidance(
            primary="직진하세요. 잘 가고 있어요.",
            pre_alert=None,
            action=None,
        )

    pos_text = _position_text(landmark)
    lm_text = _landmark_with_env(
        landmark, match_status, environment_desc,
        distance_from_start, next_dp_distance,
    )
    lm_with_particle = _particle(lm_text, "이", "가")

    primary = (
        f"{pos_text} {lm_with_particle} 보이면 잘 가고 있는 거예요. "
        f"계속 직진하세요."
    )
    return Guidance(primary=primary, pre_alert=None, action=None)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_guidance(
    dp_type: str,
    turn_type: int | None,
    selected_landmark: ScoredPoi | None,
    match_status: str | None,
    environment_desc: str | None,
    facility_visible: bool | None,
    prev_landmark_name: str | None,
    next_dp_distance: float | None,
    dest_name: str = "",
    distance_from_start: float = 0.0,
    next_action: str | None = None,
    after_landmark: ScoredPoi | None = None,
    after_match_status: str | None = None,
    after_environment_desc: str | None = None,
) -> Guidance:
    """Generate guidance text for a single DP.

    Args:
        dp_type: DP type enum value.
        turn_type: Tmap turnType code (None for VIRTUAL).
        selected_landmark: Best landmark from sequence optimizer.
        match_status: Cross-validation result.
        environment_desc: Vision environment description (Korean).
        facility_visible: Whether facility is visible in panorama.
        prev_landmark_name: Previous DP's landmark name.
        next_dp_distance: Distance to next DP in meters.
        dest_name: Destination name (for ARRIVAL).
        distance_from_start: Distance from route start.
        next_action: Next DP's action (for DEPARTURE).
        after_landmark: After-crossing landmark (for CROSSWALK).
        after_match_status: After-crossing match_status (for CROSSWALK).
        after_environment_desc: After-crossing env desc (for CROSSWALK).

    Returns:
        Guidance with primary, pre_alert, and action fields.
    """
    action = TURN_TYPE_TO_ACTION.get(turn_type, None) if turn_type else None

    if dp_type == "DEPARTURE":
        return _generate_departure(turn_type, next_action)

    if dp_type == "ARRIVAL":
        return _generate_arrival(dest_name)

    if dp_type == "DIRECTION_CHANGE":
        return _generate_direction_change(
            turn_type, action, selected_landmark, match_status,
            environment_desc, prev_landmark_name,
            distance_from_start, next_dp_distance,
        )

    if dp_type == "CROSSWALK":
        return _generate_crosswalk(
            turn_type, action, selected_landmark, match_status,
            environment_desc, facility_visible,
            distance_from_start, next_dp_distance,
            after_landmark, after_match_status, after_environment_desc,
        )

    if dp_type == "VERTICAL_MOVE":
        return _generate_vertical_move(
            turn_type, action, selected_landmark, match_status,
            environment_desc, facility_visible,
            distance_from_start, next_dp_distance,
        )

    if dp_type == "VIRTUAL":
        return _generate_virtual(
            selected_landmark, match_status,
            environment_desc, distance_from_start, next_dp_distance,
        )

    # Unknown dp_type fallback
    return Guidance(primary="직진하세요.", pre_alert=None, action=None)


def generate_all_guidance(
    decision_points: list[DecisionPoint],
    selected_landmarks: list[ScoredPoi | None],
    match_statuses: list[str | None],
    environment_descs: list[str | None],
    facility_visibles: list[bool | None],
    dest_name: str = "",
    after_landmarks: list[ScoredPoi | None] | None = None,
    after_match_statuses: list[str | None] | None = None,
    after_environment_descs: list[str | None] | None = None,
) -> list[Guidance]:
    """Generate guidance for all DPs in sequence.

    Handles prev_landmark_name chaining and next_action/next_dp_distance
    derivation automatically.

    Args:
        decision_points: ordered list of DecisionPoints.
        selected_landmarks: one per DP (None if no landmark).
        match_statuses: one per DP.
        environment_descs: one per DP.
        facility_visibles: one per DP.
        dest_name: destination name (for ARRIVAL DP).
        after_landmarks: crosswalk after-crossing landmarks (one per DP, None for non-crosswalk).
        after_match_statuses: crosswalk after-crossing match_statuses.
        after_environment_descs: crosswalk after-crossing environment descriptions.

    Returns:
        List of Guidance, one per DP.
    """
    n = len(decision_points)
    _after_landmarks = after_landmarks or [None] * n
    _after_match_statuses = after_match_statuses or [None] * n
    _after_environment_descs = after_environment_descs or [None] * n

    results: list[Guidance] = []
    prev_landmark_name: str | None = None

    for i, dp in enumerate(decision_points):
        # Compute next_dp_distance
        if i < n - 1:
            next_dp = decision_points[i + 1]
            next_dp_distance = next_dp.distance_from_start - dp.distance_from_start
        else:
            next_dp_distance = None

        # Compute next_action for DEPARTURE
        next_action: str | None = None
        if dp.dp_type == "DEPARTURE" and i < n - 1:
            next_tt = decision_points[i + 1].turn_type
            if next_tt is not None:
                next_action = TURN_TYPE_TO_ACTION.get(next_tt)

        guidance = generate_guidance(
            dp_type=dp.dp_type,
            turn_type=dp.turn_type,
            selected_landmark=selected_landmarks[i],
            match_status=match_statuses[i],
            environment_desc=environment_descs[i],
            facility_visible=facility_visibles[i],
            prev_landmark_name=prev_landmark_name,
            next_dp_distance=next_dp_distance,
            dest_name=dest_name,
            distance_from_start=dp.distance_from_start,
            next_action=next_action,
            after_landmark=_after_landmarks[i],
            after_match_status=_after_match_statuses[i],
            after_environment_desc=_after_environment_descs[i],
        )

        results.append(guidance)

        # Update prev_landmark_name for next DP
        if selected_landmarks[i] is not None:
            prev_landmark_name = selected_landmarks[i].poi.place_name
        else:
            prev_landmark_name = None

    return results
