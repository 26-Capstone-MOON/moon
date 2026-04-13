"""Route Deviation Detector — real-time GPS deviation detection.

Stateful class that processes GPS readings every 1 s and determines
whether the user has strayed from the guided pedestrian route.
"""

from __future__ import annotations

from constants import (
    CONTINUITY_SAMPLE_COUNT,
    DEVIATION_CONFIRM_DURATION_S,
    DEVIATION_DISTANCE_THRESHOLD_M,
    DEVIATION_MSG_RETURNING,
    DEVIATION_MSG_REROUTING,
    DEVIATION_MSG_WARNING,
    SPEED_THRESHOLD_KMH,
    DEVIATION_WARNING_DURATION_S,
    ContinuityTrend,
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
        self._recent_distances: list[float] = []
        self._last_gps: GpsReading | None = None

    @staticmethod
    def _validate_route(route: list[tuple[float, float]]) -> None:
        """Validate that route has at least 2 points."""
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

        Args:
            gps: Current GPS reading with lat, lng, timestamp.

        Returns:
            DeviationResult with current state, distance, trend, message, etc.
        """
        # [1] Speed filter
        if self._last_gps is not None:
            speed = calculate_speed_kmh(
                self._last_gps.lat, self._last_gps.lng, self._last_gps.timestamp,
                gps.lat, gps.lng, gps.timestamp,
            )
            if speed > SPEED_THRESHOLD_KMH:
                dist = point_to_linestring_distance(
                    gps.lat, gps.lng, self._route
                )
                print(f"[SPEED-FILTER] speed={speed:.1f}km/h > {SPEED_THRESHOLD_KMH}km/h → GPS error, keeping state={self._state}, dist={dist:.1f}")
                return DeviationResult(
                    state=self._state,
                    distance_to_route_m=dist,
                    gps_error=True,
                )

        # Accept reading
        self._last_gps = gps

        # [2] Distance calc
        dist = point_to_linestring_distance(gps.lat, gps.lng, self._route)

        if dist <= DEVIATION_DISTANCE_THRESHOLD_M:
            return self._handle_normal(dist)
        else:
            return self._handle_deviation(dist, gps.timestamp)

    def _handle_normal(self, dist: float) -> DeviationResult:
        """Reset all deviation state and return NORMAL result."""
        self._state = DeviationState.NORMAL
        self._suspect_start_time = None
        self._warning_sent = False
        self._recent_distances = []
        return DeviationResult(
            state=DeviationState.NORMAL,
            distance_to_route_m=dist,
        )

    def _handle_deviation(self, dist: float, timestamp: float) -> DeviationResult:
        """Handle GPS reading that is beyond the deviation threshold.

        Args:
            dist: Distance from GPS to route in meters.
            timestamp: GPS reading timestamp (epoch seconds).

        Returns:
            DeviationResult reflecting current deviation state.
        """
        # (a) First deviation from NORMAL
        if self._state == DeviationState.NORMAL:
            self._state = DeviationState.SUSPECTED
            self._suspect_start_time = timestamp
            self._recent_distances = [dist]
            return DeviationResult(
                state=DeviationState.SUSPECTED,
                distance_to_route_m=dist,
            )

        # (b) Compute duration
        duration = timestamp - self._suspect_start_time

        # (c) Append distance, cap to CONTINUITY_SAMPLE_COUNT
        self._recent_distances.append(dist)
        if len(self._recent_distances) > CONTINUITY_SAMPLE_COUNT:
            self._recent_distances = self._recent_distances[-CONTINUITY_SAMPLE_COUNT:]

        # (d) duration < 3s → stay SUSPECTED
        if duration < DEVIATION_WARNING_DURATION_S:
            self._state = DeviationState.SUSPECTED
            return DeviationResult(
                state=DeviationState.SUSPECTED,
                distance_to_route_m=dist,
                duration_s=duration,
            )

        # (e) duration < 5s → WARNING
        if duration < DEVIATION_CONFIRM_DURATION_S:
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

        # (f) duration >= 5s → analyze trend
        trend = self._analyze_trend()

        if trend == ContinuityTrend.DIVERGING:
            self._state = DeviationState.DEVIATED
            return DeviationResult(
                state=DeviationState.DEVIATED,
                distance_to_route_m=dist,
                duration_s=duration,
                trend=trend,
                message=DEVIATION_MSG_REROUTING,
                should_reroute=True,
            )
        elif trend == ContinuityTrend.CONVERGING:
            self._state = DeviationState.RETURNING
            return DeviationResult(
                state=DeviationState.RETURNING,
                distance_to_route_m=dist,
                duration_s=duration,
                trend=trend,
                message=DEVIATION_MSG_RETURNING,
            )
        else:
            # IRREGULAR → CONFIRMING
            self._state = DeviationState.CONFIRMING
            return DeviationResult(
                state=DeviationState.CONFIRMING,
                distance_to_route_m=dist,
                duration_s=duration,
                trend=trend,
            )

    def _analyze_trend(self) -> str:
        """Analyze recent distance samples for monotonic trend.

        Returns:
            ContinuityTrend value: DIVERGING, CONVERGING, or IRREGULAR.
        """
        if len(self._recent_distances) < CONTINUITY_SAMPLE_COUNT:
            return ContinuityTrend.IRREGULAR

        samples = self._recent_distances[-CONTINUITY_SAMPLE_COUNT:]
        d1, d2, d3 = samples[0], samples[1], samples[2]

        if d1 < d2 < d3:
            return ContinuityTrend.DIVERGING
        if d1 > d2 > d3:
            return ContinuityTrend.CONVERGING
        return ContinuityTrend.IRREGULAR

    def reset(self, route_linestring: list[tuple[float, float]] | None = None) -> None:
        """Reset all internal state. Optionally replace the route.

        Args:
            route_linestring: New route polyline. If provided, must have >= 2 points.

        Raises:
            ValueError: If new route has fewer than 2 points.
        """
        if route_linestring is not None:
            self._validate_route(route_linestring)
            self._route = route_linestring
        self._state = DeviationState.NORMAL
        self._suspect_start_time = None
        self._warning_sent = False
        self._recent_distances = []
        self._last_gps = None
