"""Geospatial utilities: haversine, bearing, point-segment distance, interpolation."""

import math

EARTH_RADIUS_M = 6_371_000.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in meters between two WGS84 coordinates."""
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return bearing in degrees (0~360) from point 1 to point 2."""
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlon = rlon2 - rlon1
    x = math.sin(dlon) * math.cos(rlat2)
    y = math.cos(rlat1) * math.sin(rlat2) - math.sin(rlat1) * math.cos(rlat2) * math.cos(dlon)
    bearing = math.degrees(math.atan2(x, y))
    return bearing % 360


def _project_onto_segment(
    px: float, py: float,
    ax: float, ay: float,
    bx: float, by: float,
) -> float:
    """Return clamped projection parameter t in [0, 1] of point P onto segment AB."""
    dx, dy = bx - ax, by - ay
    len_sq = dx * dx + dy * dy
    if len_sq == 0:
        return 0.0
    t = ((px - ax) * dx + (py - ay) * dy) / len_sq
    return max(0.0, min(1.0, t))


def point_to_segment_distance(
    plat: float, plon: float,
    alat: float, alon: float,
    blat: float, blon: float,
) -> float:
    """Return shortest distance (meters) from point P to segment AB on a sphere.

    Projects P onto the segment using a flat approximation for the parameter,
    then computes haversine distance to the projected point.
    """
    t = _project_onto_segment(plat, plon, alat, alon, blat, blon)
    clat = alat + t * (blat - alat)
    clon = alon + t * (blon - alon)
    return haversine(plat, plon, clat, clon)


def point_to_linestring_distance(
    plat: float, plon: float,
    coords: list[tuple[float, float]],
) -> float:
    """Return minimum distance (meters) from point P to a polyline."""
    if len(coords) < 2:
        if coords:
            return haversine(plat, plon, coords[0][0], coords[0][1])
        return float("inf")
    min_dist = float("inf")
    for i in range(len(coords) - 1):
        d = point_to_segment_distance(
            plat, plon,
            coords[i][0], coords[i][1],
            coords[i + 1][0], coords[i + 1][1],
        )
        if d < min_dist:
            min_dist = d
    return min_dist


def calculate_speed_kmh(
    lat1: float, lon1: float, t1: float,
    lat2: float, lon2: float, t2: float,
) -> float:
    """Return speed in km/h between two GPS readings.

    Args:
        lat1, lon1: first point coordinates.
        t1: first timestamp (epoch seconds).
        lat2, lon2: second point coordinates.
        t2: second timestamp (epoch seconds).

    Returns:
        Speed in km/h. Returns 0.0 if time difference <= 0.
    """
    dt = t2 - t1
    if dt <= 0:
        return 0.0
    dist_m = haversine(lat1, lon1, lat2, lon2)
    return dist_m / dt * 3.6


def project_distance_on_linestring(
    plat: float, plon: float,
    coords: list[tuple[float, float]],
) -> float:
    """Return cumulative distance (meters) along the linestring to the closest projection of point P.

    Finds the segment closest to P, projects P onto that segment,
    then returns the accumulated distance from the start of the linestring
    to that projection point.
    """
    if len(coords) < 2:
        return 0.0

    best_seg = 0
    best_t = 0.0
    best_dist = float("inf")
    accumulated: list[float] = [0.0]

    for i in range(len(coords) - 1):
        seg_len = haversine(coords[i][0], coords[i][1], coords[i + 1][0], coords[i + 1][1])
        accumulated.append(accumulated[-1] + seg_len)

        t = _project_onto_segment(plat, plon, coords[i][0], coords[i][1], coords[i + 1][0], coords[i + 1][1])
        proj_lat = coords[i][0] + t * (coords[i + 1][0] - coords[i][0])
        proj_lon = coords[i][1] + t * (coords[i + 1][1] - coords[i][1])
        d = haversine(plat, plon, proj_lat, proj_lon)
        if d < best_dist:
            best_dist = d
            best_seg = i
            best_t = t

    seg_len = accumulated[best_seg + 1] - accumulated[best_seg]
    return accumulated[best_seg] + best_t * seg_len


def interpolate_linestring(
    coords: list[tuple[float, float]],
    interval: float,
) -> list[tuple[float, float]]:
    """Generate points along a polyline at the given interval (meters).

    Returns intermediate points only (excludes start/end of polyline).
    """
    if len(coords) < 2 or interval <= 0:
        return []

    points: list[tuple[float, float]] = []
    accumulated = 0.0
    next_target = interval

    for i in range(len(coords) - 1):
        alat, alon = coords[i]
        blat, blon = coords[i + 1]
        seg_len = haversine(alat, alon, blat, blon)

        if seg_len == 0:
            continue

        seg_start = accumulated
        seg_end = accumulated + seg_len

        while next_target < seg_end:
            dist_from_a = next_target - seg_start
            frac = dist_from_a / seg_len
            lat = alat + frac * (blat - alat)
            lon = alon + frac * (blon - alon)
            points.append((lat, lon))
            next_target += interval

        accumulated = seg_end

    return points


def interpolate_linestring_with_distance(
    coords: list[tuple[float, float]],
    interval: float,
) -> list[tuple[float, tuple[float, float]]]:
    """Generate points along a polyline at the given interval (meters).

    Like interpolate_linestring but returns (distance_from_start, (lat, lon))
    tuples. Excludes start/end of polyline.
    """
    if len(coords) < 2 or interval <= 0:
        return []

    points: list[tuple[float, tuple[float, float]]] = []
    accumulated = 0.0
    next_target = interval

    for i in range(len(coords) - 1):
        alat, alon = coords[i]
        blat, blon = coords[i + 1]
        seg_len = haversine(alat, alon, blat, blon)

        if seg_len == 0:
            continue

        seg_start = accumulated
        seg_end = accumulated + seg_len

        while next_target < seg_end:
            frac = (next_target - seg_start) / seg_len
            lat = alat + frac * (blat - alat)
            lon = alon + frac * (blon - alon)
            points.append((next_target, (lat, lon)))
            next_target += interval

        accumulated = seg_end

    return points
