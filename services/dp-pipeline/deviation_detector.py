"""Route Deviation Detector — real-time GPS deviation detection.

Stateful class that processes GPS readings every 1 s and determines
whether the user has strayed from the guided pedestrian route.

Implements the 4-state machine from the Notion spec
("[총 정리] 경로 이탈 감지 및 재라우팅 알고리즘 문서" §3):

    NORMAL → SUSPECTED → WARNING → DEVIATED

Any state collapses back to NORMAL the moment the GPS-to-route distance
falls within DEVIATION_DISTANCE_THRESHOLD_M (≤20m).
"""

from __future__ import annotations

from constants import (
    DEVIATED_DURATION_S,
    DEVIATION_DISTANCE_THRESHOLD_M,
    DEVIATION_MSG_REROUTING,
    DEVIATION_MSG_WARNING,
    SPEED_THRESHOLD_KMH,
    WARNING_DURATION_S,
    DeviationState,
)
from geo import calculate_speed_kmh, point_to_linestring_distance
from schemas import DeviationResult, GpsReading


class DeviationDetector:
    """Stateful route deviation detector. One instance per active route session.

    Args:
        route_linestring: List of (lat, lng) tuples forming the route polyline.
            Must contain at least 2 points.

    Raises:
        ValueError: If route_linestring has fewer than 2 points.
    """

    def __init__(self, route_linestring: list[tuple[float, float]]) -> None:
        self._validate_route(route_linestring)
        self._route = route_linestring
        self._state: str = DeviationState.NORMAL
        self._suspect_start_time: float | None = None
        self._warning_sent: bool = False
        self._last_gps: GpsReading | None = None

    @staticmethod
    def _validate_route(route: list[tuple[float, float]]) -> None:
        if len(route) < 2:
            raise ValueError(
                f"Route must have at least 2 points, got {len(route)}"
            )

    @property
    def state(self) -> str:
        """Read-only current deviation state."""
        return self._state

    def update(self, gps: GpsReading) -> DeviationResult:
        """Process a GPS reading and return the deviation result.

        Decision flow (Notion §1.3):
          [1] Speed filter — discard reading if instantaneous speed > 15km/h.
              State is preserved (Notion §4.4).
          [2] Distance to route ≤ 20m → NORMAL (state + timer reset).
          [3] Distance > 20m → enter / advance the SUSPECTED→WARNING→DEVIATED chain
              based on elapsed duration.

        Args:
            gps: Current GPS reading with lat, lng, timestamp.

        Returns:
            DeviationResult with current state, distance, duration, message,
            and should_reroute flag.
        """
        # [1] Speed filter — destructive: discard reading, keep state.
        if self._last_gps is not None:
            speed = calculate_speed_kmh(
                self._last_gps.lat, self._last_gps.lng, self._last_gps.timestamp,
                gps.lat, gps.lng, gps.timestamp,
            )
            if speed > SPEED_THRESHOLD_KMH:
                dist = point_to_linestring_distance(
                    gps.lat, gps.lng, self._route
                )
                return DeviationResult(
                    state=self._state,
                    distance_to_route_m=dist,
                    gps_error=True,
                )

        # Accept reading
        self._last_gps = gps

        # [2] Distance calculation
        dist = point_to_linestring_distance(gps.lat, gps.lng, self._route)

        if dist <= DEVIATION_DISTANCE_THRESHOLD_M:
            return self._handle_normal(dist)
        return self._handle_deviation(dist, gps.timestamp)

    def _handle_normal(self, dist: float) -> DeviationResult:
        """Reset all deviation state and return NORMAL."""
        self._state = DeviationState.NORMAL
        self._suspect_start_time = None
        self._warning_sent = False
        return DeviationResult(
            state=DeviationState.NORMAL,
            distance_to_route_m=dist,
        )

    def _handle_deviation(self, dist: float, timestamp: float) -> DeviationResult:
        """Advance the SUSPECTED → WARNING → DEVIATED chain by elapsed duration."""
        # First deviation from NORMAL → enter SUSPECTED, start timer.
        if self._state == DeviationState.NORMAL:
            self._state = DeviationState.SUSPECTED
            self._suspect_start_time = timestamp
            return DeviationResult(
                state=DeviationState.SUSPECTED,
                distance_to_route_m=dist,
            )

        duration = timestamp - self._suspect_start_time

        # < 3s: stay SUSPECTED (transient).
        if duration < WARNING_DURATION_S:
            self._state = DeviationState.SUSPECTED
            return DeviationResult(
                state=DeviationState.SUSPECTED,
                distance_to_route_m=dist,
                duration_s=duration,
            )

        # 3s ≤ duration ≤ 7s: WARNING (message fires once on first entry).
        if duration <= DEVIATED_DURATION_S:
            self._state = DeviationState.WARNING
            message = None
            if not self._warning_sent:
                message = DEVIATION_MSG_WARNING
                self._warning_sent = True
            return DeviationResult(
                state=DeviationState.WARNING,
                distance_to_route_m=dist,
                duration_s=duration,
                message=message,
            )

        # > 7s: DEVIATED → trigger reroute.
        self._state = DeviationState.DEVIATED
        return DeviationResult(
            state=DeviationState.DEVIATED,
            distance_to_route_m=dist,
            duration_s=duration,
            message=DEVIATION_MSG_REROUTING,
            should_reroute=True,
        )

    def reset(self, route_linestring: list[tuple[float, float]] | None = None) -> None:
        """Reset all internal state. Optionally replace the route.

        Used after a successful reroute (Notion §7.4): the new route's
        LineString replaces the old one and all timers/flags are wiped so
        the previous trail can't influence judgments on the new path.

        Args:
            route_linestring: New route polyline. If provided, must have ≥ 2 points.

        Raises:
            ValueError: If new route has fewer than 2 points.
        """
        if route_linestring is not None:
            self._validate_route(route_linestring)
            self._route = route_linestring
        self._state = DeviationState.NORMAL
        self._suspect_start_time = None
        self._warning_sent = False
        self._last_gps = None
