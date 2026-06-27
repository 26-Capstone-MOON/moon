from __future__ import annotations

import httpx
import pytest

import candidate_service
import osm_service
import pipeline_runner
from candidate_service import merge_candidates
from poi_service import PoiResult
from schemas import DecisionPoint, Guidance, Location
from scoring_service import compute_p_h


def _poi(
    name: str,
    category: str,
    *,
    source: str = "KAKAO",
    lat: float = 37.0,
    lon: float = 127.0,
    osm_type: str | None = None,
) -> PoiResult:
    return PoiResult(
        place_name=name,
        category_group_code=category,
        category_name="",
        latitude=lat,
        longitude=lon,
        distance=5.0,
        position="FRONT",
        p_value=0.0,
        source=source,
        osm_type=osm_type,
    )


def test_normalizes_node_way_relation_and_all_supported_types():
    elements = [
        {"type": "node", "id": 1, "lat": 37.0001, "lon": 127.0,
         "tags": {"name": "한빛공원", "leisure": "park"}},
        {"type": "way", "id": 2, "center": {"lat": 37.0002, "lon": 127.0},
         "tags": {"name": "시민광장", "place": "square"}},
        {"type": "relation", "id": 3, "center": {"lat": 37.0003, "lon": 127.0},
         "tags": {"ref": "B-1", "man_made": "bridge"}},
        {"type": "node", "id": 4, "lat": 37.0004, "lon": 127.0,
         "tags": {"name": "달역", "ref": "3번 출구",
                  "railway": "subway_entrance"}},
    ]

    pois = osm_service.normalize_osm_elements(elements, 37.0, 127.0, 0.0)

    assert {poi.osm_type for poi in pois} == {
        "PARK", "SQUARE", "BRIDGE", "SUBWAY_ENTRANCE",
    }
    assert {poi.osm_id for poi in pois} == {
        "node/1", "way/2", "relation/3", "node/4",
    }
    assert all(poi.source == "OSM" for poi in pois)
    assert next(poi for poi in pois if poi.osm_type == "SUBWAY_ENTRANCE").place_name == "달역 3번 출구"


def test_excludes_unnamed_elements_and_ambiguous_subway_ref():
    elements = [
        {"type": "node", "id": 1, "lat": 37.0001, "lon": 127.0,
         "tags": {"leisure": "park"}},
        {"type": "node", "id": 2, "lat": 37.0002, "lon": 127.0,
         "tags": {"ref": "3", "railway": "subway_entrance"}},
        {"type": "node", "id": 3, "lat": 37.0003, "lon": 127.0,
         "tags": {"ref": "4", "station_name": "달역",
                  "railway": "subway_entrance"}},
    ]

    pois = osm_service.normalize_osm_elements(elements, 37.0, 127.0, 0.0)

    assert [poi.osm_id for poi in pois] == ["node/3"]
    assert pois[0].place_name == "달역 4"


@pytest.mark.asyncio
async def test_overpass_timeout_returns_empty_and_activates_backoff(monkeypatch):
    class TimeoutClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            raise httpx.ReadTimeout("slow Overpass")

    osm_service._CACHE.clear()
    osm_service._unavailable_until = 0.0
    monkeypatch.setattr(osm_service.httpx, "AsyncClient", TimeoutClient)

    assert await osm_service.search_osm_for_dp(37.0, 127.0, 0.0) == []
    assert osm_service._unavailable_until > 0.0


@pytest.mark.asyncio
async def test_empty_osm_keeps_kakao_candidates(monkeypatch):
    kakao = _poi("한빛공원", "AT4")

    async def kakao_search(*args):
        return [kakao]

    async def osm_search(*args):
        return []

    monkeypatch.setattr(candidate_service, "search_pois_for_dp", kakao_search)
    monkeypatch.setattr(candidate_service, "search_osm_for_dp", osm_search)

    assert await candidate_service.search_candidates_for_dp(37.0, 127.0, 0.0) == [kakao]


def test_deduplicates_nearby_equivalent_kakao_and_osm_candidates():
    kakao = _poi("한빛 공원", "AT4")
    osm = _poi(
        "한빛공원", "OSM_PARK", source="OSM",
        lat=37.00002, osm_type="PARK",
    )

    merged = merge_candidates([kakao], [osm])

    assert merged == [kakao]


def test_osm_types_have_explicit_nonzero_scoring_mapping():
    expected = {
        "OSM_PARK": 0.85,
        "OSM_SQUARE": 0.55,
        "OSM_BRIDGE": 0.6,
        "OSM_SUBWAY_ENTRANCE": 0.8,
    }
    for category, base_p in expected.items():
        poi = _poi("식별 요소", category, source="OSM")
        assert compute_p_h(poi, "OPEN") == pytest.approx(base_p)


@pytest.mark.asyncio
async def test_pipeline_passes_osm_candidate_to_scoring_service(monkeypatch):
    osm = _poi(
        "한빛공원", "OSM_PARK", source="OSM", osm_type="PARK",
    )
    captured: list[PoiResult] = []
    real_rank_pois = pipeline_runner.rank_pois

    async def candidates(*args):
        return [osm]

    async def open_statuses(pois):
        return {}

    def rank_spy(pois, *args, **kwargs):
        captured.extend(pois)
        return real_rank_pois(pois, *args, **kwargs)

    monkeypatch.setattr(pipeline_runner, "search_candidates_for_dp", candidates)
    monkeypatch.setattr(pipeline_runner, "fetch_is_open_statuses", open_statuses)
    monkeypatch.setattr(pipeline_runner, "rank_pois", rank_spy)
    dp = DecisionPoint(
        dp_id="dp-osm",
        dp_type="DIRECTION_CHANGE",
        turn_type=12,
        location=Location(latitude=37.0, longitude=127.0),
        guidance=Guidance(primary=""),
    )

    await pipeline_runner.run_pipeline_steps_3_to_5(
        [dp], [(37.0, 127.0), (37.001, 127.0)],
    )

    assert captured == [osm]
    assert dp.selected_landmark is not None
    assert dp.selected_landmark.category_code == "OSM_PARK"
