"""Cross-validation: POI data vs Vision results → match_status + C_bonus.

Compares POI business names against panorama Vision-recognized names to
determine existence confidence. Applies only to landmarks (not facilities).

Matching priority: exact → partial → (category match is NOT sufficient for MATCHED).
"""

from __future__ import annotations

from constants import CROSS_VALIDATION_BONUS
from poi_service import PoiResult
from schemas import CrossValidationResult

# DP types confirmed by Tmap turnType — skip cross-validation
FACILITY_DP_TYPES: set[str] = {"CROSSWALK", "VERTICAL_MOVE"}


def _normalize(name: str) -> str:
    """Strip whitespace for consistent comparison."""
    return name.strip()


def _is_exact_match(poi_name: str, vision_name: str) -> bool:
    """Check if POI name exactly equals Vision name."""
    return _normalize(poi_name) == _normalize(vision_name)


def _is_partial_match(poi_name: str, vision_name: str) -> bool:
    """Check if one name contains the other."""
    a = _normalize(poi_name)
    b = _normalize(vision_name)
    return a in b or b in a


def match_poi_against_vision(
    poi: PoiResult,
    vision_names: list[str],
) -> CrossValidationResult:
    """Match a single POI against all Vision-recognized names.

    Args:
        poi: POI from poi_service
        vision_names: Business names recognized by Vision at this DP

    Returns:
        CrossValidationResult with match_status and c_bonus.
    """
    if not vision_names:
        return CrossValidationResult(
            poi_name=poi.place_name,
            vision_name=None,
            match_status="POI_ONLY",
            c_bonus=CROSS_VALIDATION_BONUS["POI_ONLY"],
            category_group_code=poi.category_group_code,
        )

    # Priority 1: exact match
    for vn in vision_names:
        if _is_exact_match(poi.place_name, vn):
            return CrossValidationResult(
                poi_name=poi.place_name,
                vision_name=vn,
                match_status="MATCHED",
                c_bonus=CROSS_VALIDATION_BONUS["MATCHED"],
                category_group_code=poi.category_group_code,
            )

    # Priority 2: partial match
    for vn in vision_names:
        if _is_partial_match(poi.place_name, vn):
            return CrossValidationResult(
                poi_name=poi.place_name,
                vision_name=vn,
                match_status="MATCHED",
                c_bonus=CROSS_VALIDATION_BONUS["MATCHED"],
                category_group_code=poi.category_group_code,
            )

    # No name match → POI_ONLY
    return CrossValidationResult(
        poi_name=poi.place_name,
        vision_name=None,
        match_status="POI_ONLY",
        c_bonus=CROSS_VALIDATION_BONUS["POI_ONLY"],
        category_group_code=poi.category_group_code,
    )


def cross_validate_dp(
    pois: list[PoiResult],
    vision_names: list[str],
    dp_type: str,
) -> list[CrossValidationResult]:
    """Run cross-validation for all POIs at a single DP.

    Facility DPs (crosswalk, vertical move) are skipped — all POIs get
    match_status "POI_ONLY" with c_bonus 0.0 (not applicable).

    Vision names not matched to any POI are recorded as VISION_ONLY entries.

    Args:
        pois: POIs collected for this DP
        vision_names: Vision-recognized business names at this DP
        dp_type: DP type string (e.g. "DIRECTION_CHANGE", "CROSSWALK")

    Returns:
        List of CrossValidationResult — one per POI + extras for VISION_ONLY.
    """
    # Facility DP → skip cross-validation
    if dp_type in FACILITY_DP_TYPES:
        return [
            CrossValidationResult(
                poi_name=poi.place_name,
                vision_name=None,
                match_status="POI_ONLY",
                c_bonus=0.0,
                category_group_code=poi.category_group_code,
            )
            for poi in pois
        ]

    results: list[CrossValidationResult] = []
    matched_vision_names: set[str] = set()

    # Match each POI against Vision names
    for poi in pois:
        result = match_poi_against_vision(poi, vision_names)
        results.append(result)
        if result.match_status == "MATCHED" and result.vision_name:
            matched_vision_names.add(_normalize(result.vision_name))

    # Vision names not matched to any POI → VISION_ONLY
    for vn in vision_names:
        if _normalize(vn) not in matched_vision_names:
            results.append(CrossValidationResult(
                poi_name="",
                vision_name=vn,
                match_status="VISION_ONLY",
                c_bonus=CROSS_VALIDATION_BONUS["VISION_ONLY"],
                category_group_code="",
            ))

    return results


def build_match_status_map(
    results: list[CrossValidationResult],
) -> dict[str, str]:
    """Convert CrossValidationResult list to {poi_name → match_status} dict.

    Suitable for passing to scoring_service.rank_pois(match_statuses=...).

    Args:
        results: Output from cross_validate_dp

    Returns:
        Dict mapping POI name to match_status string.
    """
    return {
        r.poi_name: r.match_status
        for r in results
        if r.poi_name  # skip VISION_ONLY entries (empty poi_name)
    }
