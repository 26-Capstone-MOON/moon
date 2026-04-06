"""STEP 4. Panorama request data generation for each Decision Point.

Generates PanoramaRequest with pan angles (front/left/right) and
turnType-based is_primary correction. Server generates request data only —
actual panorama rendering is done by frontend via Naver Panorama JS SDK.
"""

from typing import Optional

from schemas import DecisionPoint, Location, PanoramaDirection, PanoramaRequest
from constants import LEFT_PRIMARY_TURN_TYPES, RIGHT_PRIMARY_TURN_TYPES


def _normalize_pan(angle: float) -> float:
    """Normalize angle to [0, 360)."""
    return angle % 360


def _determine_primary_label(turn_type: Optional[int]) -> str:
    """Return the primary direction label based on turnType.

    - Left turn / left crosswalk → LEFT
    - Right turn / right crosswalk → RIGHT
    - All others (straight, vertical, departure, arrival, virtual) → FRONT
    """
    if turn_type is not None:
        if turn_type in LEFT_PRIMARY_TURN_TYPES:
            return "LEFT"
        if turn_type in RIGHT_PRIMARY_TURN_TYPES:
            return "RIGHT"
    return "FRONT"


def build_panorama_request(dp: DecisionPoint) -> Optional[PanoramaRequest]:
    """Build a PanoramaRequest for a single DP.

    Args:
        dp: DecisionPoint with location and bearing already set.

    Returns:
        PanoramaRequest with 3 directions (front/left/right), or None if
        bearing is missing.
    """
    if dp.bearing is None:
        return None

    bearing = dp.bearing
    primary_label = _determine_primary_label(dp.turn_type)

    directions = [
        PanoramaDirection(
            pan=_normalize_pan(bearing),
            label="FRONT",
            is_primary=(primary_label == "FRONT"),
        ),
        PanoramaDirection(
            pan=_normalize_pan(bearing - 90),
            label="LEFT",
            is_primary=(primary_label == "LEFT"),
        ),
        PanoramaDirection(
            pan=_normalize_pan(bearing + 90),
            label="RIGHT",
            is_primary=(primary_label == "RIGHT"),
        ),
    ]

    return PanoramaRequest(
        location=dp.location,
        directions=directions,
    )


def generate_panorama_requests(dps: list[DecisionPoint]) -> list[DecisionPoint]:
    """Attach panorama_request to each DP in the list.

    Args:
        dps: List of DecisionPoints with bearing already calculated.

    Returns:
        Same list with panorama_request field populated on each DP.
    """
    for dp in dps:
        dp.panorama_request = build_panorama_request(dp)
    return dps
