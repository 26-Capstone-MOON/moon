"""Tmap total_distance vs Haversine cumulative distance comparison script.

Usage:
    cd services/dp-pipeline
    python compare_distance.py

Requires: TMAP_API_KEY in .env
"""

import asyncio
from geo import haversine
from tmap_service import request_pedestrian_route


# Seoul test routes (origin → destination)
TEST_ROUTES = [
    {
        "name": "강남역 → 역삼역",
        "origin": (37.4980, 127.0276),
        "dest": (37.5007, 127.0365),
    },
    {
        "name": "홍대입구역 → 합정역",
        "origin": (37.5571, 126.9236),
        "dest": (37.5496, 126.9132),
    },
    {
        "name": "서울역 → 남대문시장",
        "origin": (37.5547, 126.9707),
        "dest": (37.5594, 126.9774),
    },
    {
        "name": "건대입구역 → 성수역",
        "origin": (37.5404, 127.0696),
        "dest": (37.5445, 127.0557),
    },
    {
        "name": "잠실역 → 석촌호수",
        "origin": (37.5133, 127.1001),
        "dest": (37.5085, 127.1058),
    },
]


def haversine_total(coords: list[tuple[float, float]]) -> float:
    """Calculate total distance by summing haversine between consecutive coords."""
    total = 0.0
    for i in range(len(coords) - 1):
        total += haversine(
            coords[i][0], coords[i][1],
            coords[i + 1][0], coords[i + 1][1],
        )
    return total


async def main():
    print("=" * 70)
    print("Tmap total_distance vs Haversine cumulative distance comparison")
    print("=" * 70)
    print()
    print(f"{'경로':<25} {'Tmap(m)':>10} {'Haversine(m)':>12} {'차이(m)':>10} {'오차율':>8}")
    print("-" * 70)

    results = []

    for route in TEST_ROUTES:
        try:
            result = await request_pedestrian_route(
                origin_lat=route["origin"][0],
                origin_lng=route["origin"][1],
                dest_lat=route["dest"][0],
                dest_lng=route["dest"][1],
                dest_name=route["name"].split(" → ")[1],
            )

            tmap_dist = result.total_distance
            haver_dist = haversine_total(result.coordinates)
            diff = abs(tmap_dist - haver_dist)
            error_pct = (diff / tmap_dist * 100) if tmap_dist > 0 else 0

            results.append({
                "name": route["name"],
                "tmap": tmap_dist,
                "haversine": haver_dist,
                "diff": diff,
                "error_pct": error_pct,
                "coord_count": len(result.coordinates),
            })

            print(f"{route['name']:<25} {tmap_dist:>10.1f} {haver_dist:>12.1f} {diff:>10.1f} {error_pct:>7.2f}%")

        except Exception as e:
            print(f"{route['name']:<25} ERROR: {e}")

    if results:
        print("-" * 70)
        avg_error = sum(r["error_pct"] for r in results) / len(results)
        max_error = max(r["error_pct"] for r in results)
        avg_diff = sum(r["diff"] for r in results) / len(results)
        max_diff = max(r["diff"] for r in results)
        avg_coords = sum(r["coord_count"] for r in results) / len(results)

        print()
        print(f"평균 오차율: {avg_error:.2f}%")
        print(f"최대 오차율: {max_error:.2f}%")
        print(f"평균 절대 차이: {avg_diff:.1f}m")
        print(f"최대 절대 차이: {max_diff:.1f}m")
        print(f"평균 좌표점 수: {avg_coords:.0f}개")
        print()
        print("※ Tmap은 도로 형태를 따른 거리, Haversine은 좌표점 간 직선 거리 누적합.")
        print("  좌표점이 촘촘할수록 두 값은 수렴합니다.")


if __name__ == "__main__":
    asyncio.run(main())
