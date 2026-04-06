"""Scenario-based smoke check for the current dp-pipeline foundation.

This script does not pretend the full route pipeline is implemented.
It exercises the geometry utilities and project thresholds against a
small pedestrian scenario so developers can inspect meaningful output.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from constants import (
    ARRIVAL_DISTANCE,
    DEVIATION_DISTANCE_THRESHOLD,
    PRE_ALERT_DISTANCE,
    VIRTUAL_DP_CANDIDATE_INTERVAL,
    VIRTUAL_DP_MIN_SPACING,
    VIRTUAL_DP_THRESHOLD,
)
from geo import (
    calculate_bearing,
    haversine,
    interpolate_linestring,
    point_to_linestring_distance,
)

ROUTE_COORDS: list[tuple[float, float]] = [
    (37.5665, 126.9780),  # Seoul City Hall
    (37.5694, 126.9774),
    (37.5723, 126.9769),  # Gwanghwamun
]

NEXT_DP = ROUTE_COORDS[-1]

ROUTE_SAMPLES: dict[str, tuple[float, float]] = {
    "on_route": (37.5694, 126.9774),
    "minor_drift": (37.5694, 126.97762),
    "clear_off_route": (37.5694, 126.97840),
}

DP_APPROACH_SAMPLES: dict[str, tuple[float, float]] = {
    "outside_pre_alert": (37.57193, 126.9769),
    "inside_pre_alert": (37.57206, 126.9769),
    "inside_arrival": (37.57224, 126.9769),
}


def route_distance(coords: list[tuple[float, float]]) -> float:
    total = 0.0
    for index in range(len(coords) - 1):
        start = coords[index]
        end = coords[index + 1]
        total += haversine(start[0], start[1], end[0], end[1])
    return total


def classify_deviation(distance_m: float) -> str:
    return "ON_ROUTE" if distance_m <= DEVIATION_DISTANCE_THRESHOLD else "DEVIATION_SUSPECTED"


def classify_dp_trigger(distance_to_dp_m: float) -> str | None:
    if distance_to_dp_m <= ARRIVAL_DISTANCE:
        return "ARRIVAL"
    if distance_to_dp_m <= PRE_ALERT_DISTANCE:
        return "PRE_ALERT"
    return None


def rounded_coord(lat: float, lon: float) -> dict[str, float]:
    return {
        "latitude": round(lat, 6),
        "longitude": round(lon, 6),
    }


def build_report() -> dict:
    total_distance = route_distance(ROUTE_COORDS)

    segment_bearings = []
    for index in range(len(ROUTE_COORDS) - 1):
        start = ROUTE_COORDS[index]
        end = ROUTE_COORDS[index + 1]
        segment_bearings.append(
            {
                "segment": index + 1,
                "from": rounded_coord(start[0], start[1]),
                "to": rounded_coord(end[0], end[1]),
                "bearing_deg": round(calculate_bearing(start[0], start[1], end[0], end[1]), 2),
                "distance_m": round(haversine(start[0], start[1], end[0], end[1]), 2),
            }
        )

    virtual_dp_candidates = interpolate_linestring(ROUTE_COORDS, VIRTUAL_DP_CANDIDATE_INTERVAL)
    virtual_dp_spacing = interpolate_linestring(ROUTE_COORDS, VIRTUAL_DP_MIN_SPACING)

    route_checks = []
    for label, location in ROUTE_SAMPLES.items():
        distance_to_route = point_to_linestring_distance(location[0], location[1], ROUTE_COORDS)
        route_checks.append(
            {
                "sample": label,
                "location": rounded_coord(location[0], location[1]),
                "distance_to_route_m": round(distance_to_route, 2),
                "threshold_m": DEVIATION_DISTANCE_THRESHOLD,
                "state": classify_deviation(distance_to_route),
            }
        )

    dp_checks = []
    for label, location in DP_APPROACH_SAMPLES.items():
        distance_to_dp = haversine(location[0], location[1], NEXT_DP[0], NEXT_DP[1])
        dp_checks.append(
            {
                "sample": label,
                "location": rounded_coord(location[0], location[1]),
                "distance_to_dp_m": round(distance_to_dp, 2),
                "pre_alert_threshold_m": PRE_ALERT_DISTANCE,
                "arrival_threshold_m": ARRIVAL_DISTANCE,
                "trigger": classify_dp_trigger(distance_to_dp),
            }
        )

    return {
        "scenario": "pedestrian_foundation_smoke_check",
        "note": (
            "This validates current geometry utilities and navigation thresholds. "
            "It does not validate external API integration, landmark scoring, or "
            "full RouteResponse generation because those pipeline modules are not "
            "present in this directory yet."
        ),
        "route": {
            "start": rounded_coord(*ROUTE_COORDS[0]),
            "end": rounded_coord(*ROUTE_COORDS[-1]),
            "total_distance_m": round(total_distance, 2),
            "requires_virtual_dp_logic": total_distance > VIRTUAL_DP_THRESHOLD,
            "virtual_dp_threshold_m": VIRTUAL_DP_THRESHOLD,
            "segment_bearings": segment_bearings,
        },
        "virtual_dp_probe": {
            "candidate_interval_m": VIRTUAL_DP_CANDIDATE_INTERVAL,
            "candidate_count": len(virtual_dp_candidates),
            "candidate_preview": [
                rounded_coord(lat, lon)
                for lat, lon in virtual_dp_candidates[:5]
            ],
            "confirmed_spacing_m": VIRTUAL_DP_MIN_SPACING,
            "confirmed_preview": [
                rounded_coord(lat, lon)
                for lat, lon in virtual_dp_spacing[:5]
            ],
        },
        "deviation_probe": route_checks,
        "dp_trigger_probe": dp_checks,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a navigation-oriented smoke check.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the JSON report.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report()
    text = json.dumps(report, indent=2)

    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")

    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
