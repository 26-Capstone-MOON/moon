from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from poi_service import PoiResult
from schemas import DecisionPoint, Location, RouteResponse
from vision_schemas import (
    VisionAnalysisData,
    VisionAnalysisStatus,
    VisionDirection,
    VisionPurpose,
)

VisionCacheKey = tuple[str, str, str, str]

_PERSISTED_VISION_CACHE: dict[VisionCacheKey, VisionAnalysisData] = {}
_SPATIAL_VISION_CACHE: dict[tuple[float, float, str, str], VisionAnalysisData] = {}


def make_cache_key(
    route_id: str,
    dp_id: str,
    direction: str,
    candidate_name: str | None,
) -> VisionCacheKey:
    return (
        route_id.strip(),
        dp_id.strip(),
        direction.strip().upper(),
        (candidate_name or "").strip(),
    )


def make_spatial_cache_key(
    location: Location | tuple[float, float],
    direction: str,
    candidate_name: str | None,
) -> tuple[float, float, str, str]:
    if isinstance(location, Location):
        lat = location.latitude
        lon = location.longitude
    else:
        lat, lon = location
    return (
        round(lat, 6),
        round(lon, 6),
        direction.strip().upper(),
        (candidate_name or "").strip(),
    )


def normalize_visual_context(
    *,
    route_id: str,
    dp_id: str,
    direction: str,
    data: VisionAnalysisData,
    candidate_name: str | None = None,
    candidate_type: str | None = None,
    source: str | None = None,
) -> VisionAnalysisData:
    name = (data.candidate_name or candidate_name or "").strip() or None
    normalized_direction = VisionDirection(direction.strip().upper())
    purposes = data.purposes or []
    if not purposes:
        purposes = [VisionPurpose.SURROUNDING]
        if data.color_distinctiveness is not None or data.text_sign_ratio is not None:
            purposes.append(VisionPurpose.SALIENCE)
        if data.appearance_description or data.scene_description or data.visual_cues:
            purposes.append(VisionPurpose.APPEARANCE)

    cache_key = "|".join(make_cache_key(route_id, dp_id, normalized_direction.value, name))
    return data.model_copy(update={
        "candidate_name": name,
        "candidate_type": data.candidate_type or candidate_type,
        "direction": normalized_direction,
        "purposes": list(dict.fromkeys(purposes)),
        "source": data.source or source or "panorama-results",
        "cache_key": data.cache_key or cache_key,
        "generated_at": data.generated_at or datetime.now(timezone.utc).isoformat(),
    })


def put_visual_context(
    route_id: str,
    dp_id: str,
    direction: str,
    data: VisionAnalysisData,
    *,
    candidate_name: str | None = None,
    candidate_type: str | None = None,
    source: str | None = None,
    location: Location | tuple[float, float] | None = None,
) -> VisionAnalysisData:
    normalized = normalize_visual_context(
        route_id=route_id,
        dp_id=dp_id,
        direction=direction,
        data=data,
        candidate_name=candidate_name,
        candidate_type=candidate_type,
        source=source,
    )
    key = make_cache_key(route_id, dp_id, normalized.direction.value, normalized.candidate_name)
    _PERSISTED_VISION_CACHE[key] = normalized
    if location is not None:
        _SPATIAL_VISION_CACHE[
            make_spatial_cache_key(location, normalized.direction.value, normalized.candidate_name)
        ] = normalized
    return normalized


def get_visual_context(
    route_id: str,
    dp_id: str,
    direction: str,
    candidate_name: str | None,
    location: Location | tuple[float, float] | None = None,
) -> VisionAnalysisData | None:
    exact = _PERSISTED_VISION_CACHE.get(make_cache_key(route_id, dp_id, direction, candidate_name))
    if exact is not None:
        return exact
    route_direction = _PERSISTED_VISION_CACHE.get(make_cache_key(route_id, dp_id, direction, None))
    if route_direction is not None:
        return route_direction
    if location is None:
        return None
    spatial_exact = _SPATIAL_VISION_CACHE.get(
        make_spatial_cache_key(location, direction, candidate_name)
    )
    if spatial_exact is not None:
        return spatial_exact
    return _SPATIAL_VISION_CACHE.get(make_spatial_cache_key(location, direction, None))


def find_visual_context_for_poi(
    route_id: str | None,
    dp_id: str,
    poi: PoiResult,
    dp_location: Location | tuple[float, float] | None = None,
) -> VisionAnalysisData | None:
    if not route_id:
        return None
    candidates = [
        poi.position,
        "FRONT",
        "LEFT",
        "RIGHT",
    ]
    for direction in dict.fromkeys(candidates):
        result = get_visual_context(route_id, dp_id, direction, poi.place_name, dp_location)
        if result is not None and result.analysis_status == VisionAnalysisStatus.ANALYZED:
            return result
    return None


def iter_dp_visual_contexts(route_id: str, dp_id: str) -> Iterable[VisionAnalysisData]:
    prefix = (route_id.strip(), dp_id.strip())
    for key, value in _PERSISTED_VISION_CACHE.items():
        if key[:2] == prefix:
            yield value


def visual_v_score(data: VisionAnalysisData | None) -> float | None:
    if data is None or data.analysis_status != VisionAnalysisStatus.ANALYZED:
        return None
    if data.color_distinctiveness is None:
        return None

    candidate_type = (data.candidate_type or "").upper()
    if candidate_type == "BUILDING":
        return data.color_distinctiveness
    if data.text_sign_ratio is None:
        return None
    return data.color_distinctiveness * data.text_sign_ratio


def visual_description(data: VisionAnalysisData | None) -> str | None:
    if data is None or data.analysis_status != VisionAnalysisStatus.ANALYZED:
        return None
    return data.appearance_description or data.scene_description


def attach_visual_context_to_route(route: RouteResponse, dp_id: str) -> bool:
    changed = False
    for dp in route.decision_points:
        if dp.dp_id != dp_id or dp.selected_landmark is None:
            continue
        contexts = list(iter_dp_visual_contexts(route.route_id, dp.dp_id))
        selected = None
        for context in contexts:
            if context.candidate_name == dp.selected_landmark.name:
                selected = context
                break
        if selected is None and contexts:
            selected = contexts[0]
        if selected is None:
            continue
        dp.selected_landmark.visual_context = selected
        desc = visual_description(selected)
        if desc:
            dp.selected_landmark.appearance = desc
            if dp.guidance and desc not in dp.guidance.primary:
                dp.guidance.primary = f"{desc} {dp.guidance.primary}"
        changed = True
    return changed
