"""Shared pipeline runner — STEP 3 (POI scoring) → STEP 4 (sequence opt)
→ STEP 5 (panorama + guidance generation).

Used by both initial route creation (`main._build_route_response`) and
rerouting (`rerouting_service.reroute`) so a rerouted route gets the same
landmark-quality guidance as a freshly created one (Notion §7.2 ④).

The runner mutates `decision_points` in place: filling `selected_landmark`,
`panorama_request`, and `guidance` fields. STEP 1 (DP extraction) and
STEP 2 (midpoint insertion) must already be done before calling this.
"""

from __future__ import annotations

from constants import (
    LEFT_PRIMARY_TURN_TYPES,
    RIGHT_PRIMARY_TURN_TYPES,
    TURN_TYPE_TO_ACTION,
)
from geo import point_to_segment_distance
from guidance_generator import generate_guidance
from places_service import fetch_is_open_statuses, poi_identity_key
from poi_service import (
    PoiResult,
    search_pois_for_crosswalk,
    search_pois_for_dp,
)
from schemas import (
    DecisionPoint,
    Location,
    PanoramaDirection,
    PanoramaRequest,
    SelectedLandmark,
)
from scoring_service import ScoredPoi, rank_pois, select_landmark
from sequence_optimizer import optimize_sequence


# ---------------------------------------------------------------------------
# Geometry / panorama helpers
# ---------------------------------------------------------------------------

def get_dp_bearing(
    dp: DecisionPoint,
    route_coordinates: list[tuple[float, float]],
) -> float:
    """Calculate travel bearing at a DP location on the route.

    Uses the route segment whose perpendicular distance to the DP is the
    smallest. Falls back to 0.0 when the route has fewer than 2 points.
    """
    from geo import calculate_bearing  # local import keeps top-level minimal

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


def _primary_label_for_turn_type(turn_type: int | None) -> str:
    """Determine panorama isPrimary direction from turnType."""
    if turn_type is None:
        return "FRONT"
    if turn_type in LEFT_PRIMARY_TURN_TYPES:
        return "LEFT"
    if turn_type in RIGHT_PRIMARY_TURN_TYPES:
        return "RIGHT"
    return "FRONT"


def build_3dir_panorama(location: Location, turn_type: int | None) -> PanoramaRequest:
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


# ---------------------------------------------------------------------------
# Landmark / scoring helpers
# ---------------------------------------------------------------------------

def resolve_is_open_status(poi: PoiResult, is_open_map: dict[str, str]) -> str:
    """Resolve isOpen status using the stable POI identity key."""
    return is_open_map.get(
        poi_identity_key(poi),
        is_open_map.get(poi.place_name, "UNKNOWN"),
    )


def scored_from_selected_landmark(landmark: SelectedLandmark) -> ScoredPoi:
    """Synthesize a ScoredPoi from an existing SelectedLandmark.

    Used so already-finalized DPs (VIRTUAL from midpoint_service, or
    cache-reused DPs in rerouting) can participate in the
    sequence-optimizer chain. The single-candidate list ensures the
    optimizer cannot swap their landmark.
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


def build_selected_landmark(
    scored: ScoredPoi,
    is_open_map: dict[str, str],
) -> SelectedLandmark:
    """Serialize a scored POI into the public SelectedLandmark model."""
    is_open_status = resolve_is_open_status(scored.poi, is_open_map)
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


# ---------------------------------------------------------------------------
# STEP 3-5 runner
# ---------------------------------------------------------------------------

async def run_pipeline_steps_3_to_5(
    decision_points: list[DecisionPoint],
    route_coordinates: list[tuple[float, float]],
    dest_name: str = "",
    skip_dp_ids: set[str] | None = None,
) -> None:
    """Run STEP 3 → STEP 4 → STEP 5 on a finalized DP list.

    STEP 3 — POI search + per-DP top-k ranking.
    STEP 4 — Sequence optimization (name dedup + zigzag fix).
    STEP 5 — Apply optimized selection, build panorama, generate guidance.

    Args:
        decision_points: DPs after STEP 1 + STEP 2. Mutated in place.
        route_coordinates: Route polyline as (lat, lon) tuples.
        dest_name: Destination name (used by ARRIVAL guidance).
        skip_dp_ids: DP IDs whose selected_landmark / panorama / guidance
            are already populated (e.g. cache-reused from a previous route
            during rerouting). They participate in the sequence-optimizer
            chain via a single fixed candidate but are not overwritten.

    Returns:
        None — mutates decision_points in place.
    """
    skip_ids = skip_dp_ids or set()

    # ----- STEP 3: POI search + per-DP ranking -----
    dp_candidates: list[list[ScoredPoi]] = []
    crosswalk_after_per_dp: dict[str, ScoredPoi | None] = {}
    is_open_per_dp: dict[str, dict[str, str]] = {}

    for dp in decision_points:
        # VIRTUAL DPs (midpoint_service-finalized) and cache-reused DPs
        # (rerouting): feed existing landmark as a single fixed candidate.
        if dp.dp_type == "VIRTUAL" or dp.dp_id in skip_ids:
            if dp.selected_landmark is not None:
                dp_candidates.append(
                    [scored_from_selected_landmark(dp.selected_landmark)]
                )
            else:
                dp_candidates.append([])
            is_open_per_dp[dp.dp_id] = {}
            continue

        if dp.dp_type in ("DEPARTURE", "ARRIVAL"):
            dp_candidates.append([])
            is_open_per_dp[dp.dp_id] = {}
            continue

        bearing = get_dp_bearing(dp, route_coordinates)

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

    # ----- STEP 4: Sequence optimization -----
    optimized_landmarks = optimize_sequence(dp_candidates)

    print(f"\n{'='*60}")
    print(f"[STEP4] 시퀀스 최적화 결과 ({len(optimized_landmarks)}개)")
    print(f"{'='*60}")
    for dp, sel in zip(decision_points, optimized_landmarks):
        name = sel.poi.place_name if sel else "NONE"
        score = f"{sel.s_final:.2f}" if sel else "—"
        print(f"  dp={dp.dp_id}, type={dp.dp_type}, selected={name}, score={score}")
    print(f"{'='*60}")

    # ----- STEP 5: Apply selection + panorama + guidance -----
    prev_landmark_name: str | None = None
    for i, dp in enumerate(decision_points):
        # VIRTUAL DPs: midpoint_service finalized landmark+guidance+panorama.
        # Cache-reused DPs: previous route already populated everything.
        # Both: just track prev_landmark_name for chaining.
        if dp.dp_type == "VIRTUAL" or dp.dp_id in skip_ids:
            if dp.selected_landmark is not None:
                prev_landmark_name = dp.selected_landmark.name
            else:
                prev_landmark_name = None
            continue

        selected = optimized_landmarks[i]
        is_open_map = is_open_per_dp.get(dp.dp_id, {})
        after_scored = crosswalk_after_per_dp.get(dp.dp_id)

        # Apply optimized selection.
        # CROSSWALK fallback: if before-crossing landmark is missing, surface
        # the after-crossing one in the API output instead of leaving it null.
        if selected is not None:
            dp.selected_landmark = build_selected_landmark(selected, is_open_map)
        elif dp.dp_type == "CROSSWALK" and after_scored is not None:
            dp.selected_landmark = build_selected_landmark(after_scored, is_open_map)

        # Panorama: 3-direction for non-DEPARTURE/ARRIVAL DPs, front-only otherwise.
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
                dp.panorama_request = build_3dir_panorama(
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
            dest_name=dest_name,
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
