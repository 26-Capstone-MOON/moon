"""STEP 2: Midpoint (Virtual DP) insertion for long straight segments.

Scores candidates with P(h) × (D(w) + U) — C_bonus excluded at midpoint stage.
Selected midpoints include SelectedLandmark, Korean guidance, and front-only panorama.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field

from constants import (
    VIRTUAL_DP_CANDIDATE_INTERVAL,
    VIRTUAL_DP_MIN_SPACING,
    VIRTUAL_DP_THRESHOLD,
)
from geo import (
    calculate_bearing,
    haversine,
    interpolate_linestring_with_distance,
    point_to_segment_distance,
)
from places_service import fetch_is_open_statuses, poi_identity_key
from poi_service import PoiResult, search_pois_for_dp
from schemas import (
    DecisionPoint,
    Guidance,
    Location,
    PanoramaDirection,
    PanoramaRequest,
    SelectedLandmark,
)
from scoring_service import compute_d_w, compute_p_h, compute_uniqueness

MAX_CONCURRENT_POI_SEARCHES = 5


# ---------------------------------------------------------------------------
# Internal candidate dataclass
# ---------------------------------------------------------------------------

@dataclass
class _ScoredCandidate:
    """Midpoint candidate with POI scoring results."""

    dist_from_start: float
    lat: float
    lon: float
    score: float
    best_poi: PoiResult | None
    all_pois: list[PoiResult] = field(default_factory=list)
    bearing: float = 0.0
    search_radius: float = 50.0


# ---------------------------------------------------------------------------
# Gap detection
# ---------------------------------------------------------------------------

def _find_gaps(
    decision_points: list[DecisionPoint],
) -> list[tuple[int, int, float]]:
    """Find consecutive DP pairs with gap > VIRTUAL_DP_THRESHOLD.

    Args:
        decision_points: Sorted list of DPs by distance_from_start.

    Returns:
        List of (index_a, index_b, gap_distance) tuples.
    """
    gaps: list[tuple[int, int, float]] = []
    for i in range(len(decision_points) - 1):
        gap = (
            decision_points[i + 1].distance_from_start
            - decision_points[i].distance_from_start
        )
        if gap > VIRTUAL_DP_THRESHOLD:
            gaps.append((i, i + 1, gap))
    return gaps


# ---------------------------------------------------------------------------
# Route sub-segment extraction
# ---------------------------------------------------------------------------

def _extract_sub_coords(
    route_coordinates: list[tuple[float, float]],
    start_distance: float,
    end_distance: float,
) -> list[tuple[float, float]]:
    """Extract route coordinates between two distance-from-start values.

    Walks along route_coordinates, accumulating haversine distances.
    Interpolates boundary points at exact start_distance and end_distance.

    Args:
        route_coordinates: Full route polyline as (lat, lon) tuples.
        start_distance: Start distance from route origin (meters).
        end_distance: End distance from route origin (meters).

    Returns:
        Sub-segment coordinates including interpolated boundary points.
    """
    if len(route_coordinates) < 2:
        return list(route_coordinates)

    result: list[tuple[float, float]] = []
    accumulated = 0.0

    for i in range(len(route_coordinates) - 1):
        alat, alon = route_coordinates[i]
        blat, blon = route_coordinates[i + 1]
        seg_len = haversine(alat, alon, blat, blon)

        if seg_len == 0:
            continue

        seg_start = accumulated
        seg_end = accumulated + seg_len

        # Interpolate start boundary
        if seg_start < start_distance <= seg_end and not result:
            frac = (start_distance - seg_start) / seg_len
            lat = alat + frac * (blat - alat)
            lon = alon + frac * (blon - alon)
            result.append((lat, lon))

        # Include original coordinates within range
        if accumulated >= start_distance and accumulated <= end_distance:
            if not result or result[-1] != (alat, alon):
                result.append((alat, alon))

        # Interpolate end boundary
        if seg_start < end_distance <= seg_end:
            frac = (end_distance - seg_start) / seg_len
            lat = alat + frac * (blat - alat)
            lon = alon + frac * (blon - alon)
            if not result or result[-1] != (lat, lon):
                result.append((lat, lon))
            break

        accumulated = seg_end

    return result


# ---------------------------------------------------------------------------
# Bearing helper
# ---------------------------------------------------------------------------

def _bearing_at_point(
    lat: float,
    lon: float,
    route_coordinates: list[tuple[float, float]],
) -> float:
    """Calculate travel bearing at a point by finding the nearest route segment.

    Args:
        lat: Point latitude.
        lon: Point longitude.
        route_coordinates: Full route polyline.

    Returns:
        Bearing in degrees (0~360) of the nearest segment.
    """
    if len(route_coordinates) < 2:
        return 0.0

    min_dist = float("inf")
    best_idx = 0

    for i in range(len(route_coordinates) - 1):
        d = point_to_segment_distance(
            lat, lon,
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


# ---------------------------------------------------------------------------
# Midpoint POI scoring — P(h) × (D(w) + U), no C_bonus
# ---------------------------------------------------------------------------

def _score_midpoint_poi(
    poi: PoiResult,
    all_pois: list[PoiResult],
    weather: str,
    is_open_status: str = "UNKNOWN",
    search_radius: float = 50.0,
) -> float:
    """Score POI for midpoint candidate ranking.

    Uses (P × h × U) × (D × w). C is excluded at midpoint stage (no Vision).

    Args:
        poi: Target POI.
        all_pois: All POIs near this candidate (for uniqueness).
        weather: WeatherCondition enum value.
        is_open_status: "OPEN", "CLOSED", or "UNKNOWN".
        search_radius: Adaptive search radius (MD) used during POI collection.

    Returns:
        Midpoint score (higher is better).
    """
    p_h = compute_p_h(poi, is_open_status)
    d_w = compute_d_w(poi.distance, weather, search_radius)
    u = compute_uniqueness(poi, all_pois)
    return (p_h * u) * d_w


# ---------------------------------------------------------------------------
# Korean guidance text helpers
# ---------------------------------------------------------------------------

def _subject_particle(name: str) -> str:
    """Return Korean subject particle (이/가) based on final consonant (받침).

    Args:
        name: POI name string.

    Returns:
        "이" if last character has 받침, "가" otherwise.
    """
    if not name:
        return "이"
    last_char = name[-1]
    if '가' <= last_char <= '힣':
        code = ord(last_char) - 0xAC00
        if code % 28 > 0:
            return "이"
        return "가"
    return "이"


def _build_midpoint_guidance(poi: PoiResult) -> Guidance:
    """Generate Virtual DP guidance text from selected POI.

    Pattern: "{위치}에 {이름}이/가 보이면 잘 가고 있는 거예요. 계속 직진하세요."

    Args:
        poi: The selected landmark POI.

    Returns:
        Guidance with Korean primary text, no pre_alert or action.
    """
    position_text = {"LEFT": "왼쪽", "RIGHT": "오른쪽", "FRONT": "앞쪽"}.get(
        poi.position, "근처"
    )
    particle = _subject_particle(poi.place_name)
    primary = (
        f"{position_text}에 {poi.place_name}{particle} 보이면 "
        f"잘 가고 있는 거예요. 계속 직진하세요."
    )
    return Guidance(primary=primary, pre_alert=None, action=None)


# ---------------------------------------------------------------------------
# Panorama + Landmark builders
# ---------------------------------------------------------------------------

def _build_front_only_panorama(lat: float, lon: float) -> PanoramaRequest:
    """Create front-only panorama request for virtual DP.

    Args:
        lat: Virtual DP latitude.
        lon: Virtual DP longitude.

    Returns:
        PanoramaRequest with single FRONT direction.
    """
    return PanoramaRequest(
        location=Location(latitude=lat, longitude=lon),
        directions=[PanoramaDirection(pan=0.0, label="FRONT", is_primary=True)],
    )


def _poi_to_landmark(
    poi: PoiResult,
    score: float,
    is_open_status: str = "UNKNOWN",
) -> SelectedLandmark:
    """Convert a PoiResult to SelectedLandmark for a virtual DP.

    Args:
        poi: The selected POI.
        score: Final computed score.
        is_open_status: "OPEN", "CLOSED", or "UNKNOWN".

    Returns:
        SelectedLandmark with POI_ONLY match_status.
    """
    return SelectedLandmark(
        name=poi.place_name,
        category_code=poi.category_group_code,
        position=poi.position,
        distance=poi.distance,
        score=round(score, 4),
        match_status="POI_ONLY",
        is_open=is_open_status == "OPEN",
    )


# ---------------------------------------------------------------------------
# Greedy candidate selection with spacing
# ---------------------------------------------------------------------------

def _greedy_select(
    candidates: list[_ScoredCandidate],
    min_spacing: float,
    start_distance: float,
    end_distance: float,
) -> list[_ScoredCandidate]:
    """Greedily select candidates enforcing minimum spacing.

    Candidates must be sorted by score descending before calling.

    Args:
        candidates: Scored candidates sorted by score desc.
        min_spacing: Minimum distance between selected candidates and DPs.
        start_distance: Distance of the preceding DP.
        end_distance: Distance of the following DP.

    Returns:
        Selected candidates meeting spacing requirements.
    """
    selected: list[_ScoredCandidate] = []

    for cand in candidates:
        # Check spacing from bounding DPs
        if cand.dist_from_start - start_distance < min_spacing:
            continue
        if end_distance - cand.dist_from_start < min_spacing:
            continue

        # Check spacing from already selected candidates
        too_close = any(
            abs(cand.dist_from_start - sel.dist_from_start) < min_spacing
            for sel in selected
        )
        if not too_close:
            selected.append(cand)

    return selected


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def insert_midpoints(
    decision_points: list[DecisionPoint],
    route_coordinates: list[tuple[float, float]],
    weather: str = "CLEAR",
) -> list[DecisionPoint]:
    """Insert Virtual DPs into gaps > 200m between consecutive DPs.

    For each qualifying gap:
    1. Generate candidates at 30m intervals along route segment.
    2. Search POIs at each candidate and score with P(h) × (D(w) + U).
    3. Greedily select top candidates with >= 100m spacing.
    4. If ALL candidates lack POIs, insert 1 geometric midpoint as fallback.
    5. Build SelectedLandmark, Korean guidance, and front-only panorama.

    Args:
        decision_points: Sorted DPs from dp_extractor.
        route_coordinates: Full route polyline as (lat, lon) tuples.
        weather: WeatherCondition enum value for D(w) scoring.

    Returns:
        New list with virtual DPs inserted, sorted by distance_from_start.
    """
    if len(decision_points) < 2:
        return list(decision_points)

    gaps = _find_gaps(decision_points)
    if not gaps:
        return list(decision_points)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_POI_SEARCHES)
    virtual_dps: list[DecisionPoint] = []

    for idx_a, idx_b, _ in gaps:
        dp_a = decision_points[idx_a]
        dp_b = decision_points[idx_b]

        sub_coords = _extract_sub_coords(
            route_coordinates,
            dp_a.distance_from_start,
            dp_b.distance_from_start,
        )
        if len(sub_coords) < 2:
            continue

        # Generate candidates along sub-segment
        candidates_raw = interpolate_linestring_with_distance(
            sub_coords, VIRTUAL_DP_CANDIDATE_INTERVAL,
        )
        if not candidates_raw:
            continue

        # Convert sub-segment distances to route-level distances
        candidates_with_route_dist = [
            (dp_a.distance_from_start + dist, lat, lon)
            for dist, (lat, lon) in candidates_raw
        ]

        # Score each candidate by POI search
        async def _score_one(
            dist: float, lat: float, lon: float,
        ) -> _ScoredCandidate:
            async with semaphore:
                bearing = _bearing_at_point(lat, lon, route_coordinates)
                pois, sr = await search_pois_for_dp(lat, lon, bearing)

            return _ScoredCandidate(
                dist_from_start=dist,
                lat=lat,
                lon=lon,
                score=0.0,
                best_poi=None,
                all_pois=pois,
                bearing=bearing,
                search_radius=sr,
            )

        scored = await asyncio.gather(*[
            _score_one(d, la, lo) for d, la, lo in candidates_with_route_dist
        ])
        scored_list: list[_ScoredCandidate] = list(scored)

        unique_pois: dict[str, PoiResult] = {}
        for cand in scored_list:
            for poi in cand.all_pois:
                unique_pois.setdefault(poi_identity_key(poi), poi)

        is_open_map = await fetch_is_open_statuses(list(unique_pois.values()))

        for cand in scored_list:
            if not cand.all_pois:
                continue

            best_score = -1.0
            best_poi: PoiResult | None = None
            for poi in cand.all_pois:
                is_open_status = is_open_map.get(
                    poi_identity_key(poi),
                    is_open_map.get(poi.place_name, "UNKNOWN"),
                )
                score = _score_midpoint_poi(
                    poi,
                    cand.all_pois,
                    weather,
                    is_open_status,
                    search_radius=cand.search_radius,
                )
                if score > best_score:
                    best_score = score
                    best_poi = poi

            cand.score = max(best_score, 0.0)
            cand.best_poi = best_poi

        # Fallback: if NO candidate has POIs, insert 1 geometric midpoint
        any_has_poi = any(c.best_poi is not None for c in scored_list)

        if not any_has_poi:
            mid_dist = (dp_a.distance_from_start + dp_b.distance_from_start) / 2
            closest = min(
                scored_list,
                key=lambda c: abs(c.dist_from_start - mid_dist),
            )
            virtual_dps.append(DecisionPoint(
                dp_id=f"dp-{uuid.uuid4().hex[:8]}",
                dp_type="VIRTUAL",
                turn_type=None,
                location=Location(latitude=closest.lat, longitude=closest.lon),
                bearing=closest.bearing,
                distance_from_start=closest.dist_from_start,
                guidance=Guidance(
                    primary="직진하세요.",
                    pre_alert=None,
                    action=None,
                ),
                selected_landmark=None,
                panorama_request=_build_front_only_panorama(
                    closest.lat, closest.lon,
                ),
            ))
            continue

        # Sort by score descending, greedy select with spacing
        scored_list.sort(key=lambda c: c.score, reverse=True)
        selected = _greedy_select(
            scored_list,
            VIRTUAL_DP_MIN_SPACING,
            dp_a.distance_from_start,
            dp_b.distance_from_start,
        )

        if not selected:
            continue

        # Build virtual DPs with landmark, guidance, and panorama
        for cand in selected:
            if cand.best_poi is not None:
                is_open_status = is_open_map.get(
                    poi_identity_key(cand.best_poi),
                    is_open_map.get(cand.best_poi.place_name, "UNKNOWN"),
                )
                final_score = _score_midpoint_poi(
                    cand.best_poi, cand.all_pois, weather, is_open_status,
                    search_radius=cand.search_radius,
                )
                landmark = _poi_to_landmark(
                    cand.best_poi, final_score, is_open_status,
                )
                guidance = _build_midpoint_guidance(cand.best_poi)
            else:
                landmark = None
                guidance = Guidance(
                    primary="직진하세요.",
                    pre_alert=None,
                    action=None,
                )

            virtual_dps.append(DecisionPoint(
                dp_id=f"dp-{uuid.uuid4().hex[:8]}",
                dp_type="VIRTUAL",
                turn_type=None,
                location=Location(latitude=cand.lat, longitude=cand.lon),
                bearing=cand.bearing,
                distance_from_start=cand.dist_from_start,
                guidance=guidance,
                selected_landmark=landmark,
                panorama_request=_build_front_only_panorama(cand.lat, cand.lon),
            ))

    # Merge and sort
    result = list(decision_points) + virtual_dps
    result.sort(key=lambda dp: dp.distance_from_start)
    return result
