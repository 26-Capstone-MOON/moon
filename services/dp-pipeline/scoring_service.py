"""STEP 5: Landmark scoring — S_final = (P × h × U) × (D × w) × C.

Scores POI candidates for each DP and selects the best landmark.
All parameters are multiplicative. C defaults to POI_ONLY (1.2) until
Vision cross-validation is available.
"""

from __future__ import annotations

from dataclasses import dataclass

from constants import (
    CATEGORY_P_VALUES,
    CROSS_VALIDATION_COEFFICIENT,
    DEFAULT_P_VALUE,
    DEFAULT_POI_RADIUS,
    IS_OPEN_COEFFICIENT,
    UNIQUENESS_DEFAULT,
    UNIQUENESS_SCORES,
    WEATHER_W_MOD,
    WeatherCondition,
)
from places_service import poi_identity_key
from poi_service import PoiResult

# ---------------------------------------------------------------------------
# Sub-classification overrides (keyword in category_name)
# ---------------------------------------------------------------------------
# Each entry: (keyword, override_P)
# Checked against segments split by " > " in category_name.

SUB_CLASSIFICATION: dict[str, list[tuple[str, float]]] = {
    "MT1": [
        ("대형마트", 1.0),
        ("대형슈퍼", 0.85),
        ("슈퍼마켓", 0.65),
    ],
    "PO3": [
        ("시청", 0.95), ("구청", 0.95), ("군청", 0.95),
        ("경찰서", 0.90), ("파출소", 0.90),
        ("소방서", 0.90),
        ("주민센터", 0.85),
        ("우체국", 0.85),
        ("도서관", 0.8),
    ],
    "BK9": [
        ("저축은행", 0.45),
        ("365", 0.4), ("ATM", 0.4),
    ],
    "SC4": [
        ("대학교", 0.95),
        ("초등학교", 0.85), ("중학교", 0.85), ("고등학교", 0.85),
    ],
    "HP8": [
        ("종합병원", 0.9), ("대학병원", 0.9),
        ("치과", 0.55), ("안과", 0.55), ("피부과", 0.55), ("한의원", 0.55),
    ],
    "CT1": [
        ("CGV", 0.75), ("메가박스", 0.75), ("롯데시네마", 0.75),
        ("세종문화회관", 0.7), ("예술의전당", 0.7),
        ("국립중앙박물관", 0.7), ("국립", 0.7),
        ("문예회관", 0.55), ("아트센터", 0.55),
        ("시립", 0.5), ("구립", 0.5),
        ("소극장", 0.3),
        ("갤러리", 0.3),
        ("독립영화", 0.15), ("예술영화", 0.15),
    ],
    "AT4": [
        ("공원", 0.85),
    ],
    "AC5": [
        ("메가스터디", 0.45), ("대성", 0.45), ("종로", 0.45),
    ],
    "AD5": [
        ("호텔", 0.4),
        ("모텔", 0.25),
    ],
    "PK6": [
        ("공영", 0.4),
        ("민영", 0.15),
    ],
}

# Franchise keywords for CE7 (cafe) and FD6 (restaurant)
FRANCHISE_CAFE_KEYWORDS: list[str] = [
    "스타벅스", "투썸플레이스", "이디야", "메가커피", "컴포즈",
    "빽다방", "할리스", "파스쿠찌", "커피빈", "탐앤탐스",
    "엔제리너스", "폴바셋", "더벤티", "매머드커피",
]

FRANCHISE_RESTAURANT_KEYWORDS: list[str] = [
    "맥도날드", "버거킹", "롯데리아", "KFC", "맘스터치",
    "파파이스", "서브웨이", "도미노", "피자헛", "BBQ",
    "교촌", "BHC", "굽네", "네네", "김밥천국",
    "한솥", "본죽", "죽이야기", "CoCo", "코코",
]


@dataclass
class ScoredPoi:
    """POI with full scoring breakdown."""

    poi: PoiResult
    p_h: float       # P × h (category recognition × business hours)
    d_w: float       # D × w (distance fitness × weather)
    u: float         # Uniqueness
    c: float         # Cross-validation coefficient (multiplicative)
    s_final: float   # (P × h × U) × (D × w) × C


# ---------------------------------------------------------------------------
# P(h) — Category recognition x business hour correction
# ---------------------------------------------------------------------------

def _get_sub_p(category_code: str, category_name: str) -> float | None:
    """Check sub-classification override for a POI.

    Parses category_name by " > " and checks keywords.

    Args:
        category_code: Kakao category_group_code
        category_name: Full category path (e.g. "음식점 > 카페 > 스타벅스")

    Returns:
        Override P value if matched, None otherwise.
    """
    overrides = SUB_CLASSIFICATION.get(category_code)
    if not overrides:
        return None

    segments = category_name.split(" > ")
    for keyword, sub_p in overrides:
        for segment in segments:
            if keyword in segment:
                return sub_p
    return None


def _is_franchise_cafe(place_name: str, category_name: str) -> bool:
    """Check if a cafe is a franchise brand."""
    text = f"{place_name} {category_name}"
    return any(kw in text for kw in FRANCHISE_CAFE_KEYWORDS)


def _is_franchise_restaurant(place_name: str, category_name: str) -> bool:
    """Check if a restaurant is a franchise brand."""
    text = f"{place_name} {category_name}"
    return any(kw in text for kw in FRANCHISE_RESTAURANT_KEYWORDS)


def compute_p_h(
    poi: PoiResult,
    is_open_status: str = "UNKNOWN",
) -> float:
    """Compute P(h) = base_or_sub_P * h_multiplier.

    Args:
        poi: POI result with category info
        is_open_status: "OPEN", "CLOSED", or "UNKNOWN"

    Returns:
        P(h) value.
    """
    base_p = CATEGORY_P_VALUES.get(poi.category_group_code, DEFAULT_P_VALUE)

    # Sub-classification override
    sub_p = _get_sub_p(poi.category_group_code, poi.category_name)
    if sub_p is not None:
        base_p = sub_p
    else:
        # Franchise check for CE7/FD6
        if poi.category_group_code == "CE7":
            base_p = 0.7 if _is_franchise_cafe(poi.place_name, poi.category_name) else 0.3
        elif poi.category_group_code == "FD6":
            base_p = 0.6 if _is_franchise_restaurant(poi.place_name, poi.category_name) else 0.25

    h_multiplier = IS_OPEN_COEFFICIENT.get(is_open_status, 0.7)
    return base_p * h_multiplier


# ---------------------------------------------------------------------------
# D(w) — Distance fitness x weather correction
# ---------------------------------------------------------------------------

def compute_d_w(
    distance: float,
    weather: str = "CLEAR",
    search_radius: float = DEFAULT_POI_RADIUS,
) -> float:
    """Compute D × w = (1 - d/MD) × w_mod.

    Args:
        distance: Straight-line distance from DP to POI (meters).
        weather: WeatherCondition enum value.
        search_radius: Adaptive search radius (MD) used during POI collection.

    Returns:
        D × w value, clamped to >= 0.
    """
    md = max(search_radius, 1.0)  # avoid division by zero
    d_ratio = max(0.0, 1.0 - distance / md)
    w_mod = WEATHER_W_MOD.get(weather, 1.0)
    return d_ratio * w_mod


# ---------------------------------------------------------------------------
# U — Uniqueness
# ---------------------------------------------------------------------------

def compute_uniqueness(
    poi: PoiResult,
    all_pois: list[PoiResult],
) -> float:
    """Compute uniqueness score based on same-category count.

    Prefers the fixed 100m same-category count attached during POI collection.
    Falls back to counting POIs in the provided list when the fixed-radius
    context is unavailable (e.g. unit tests using handcrafted POIs).

    Args:
        poi: Target POI
        all_pois: All POIs near this DP

    Returns:
        U value (1.0 / 0.7 / 0.4 / 0.2).
    """
    same_count = poi.same_category_count_100m
    if same_count is None:
        same_count = sum(
            1 for p in all_pois
            if p.category_group_code == poi.category_group_code
        )
    return UNIQUENESS_SCORES.get(same_count, UNIQUENESS_DEFAULT)


# ---------------------------------------------------------------------------
# Score computation
# ---------------------------------------------------------------------------

def score_poi(
    poi: PoiResult,
    all_pois: list[PoiResult],
    weather: str = "CLEAR",
    is_open_status: str = "UNKNOWN",
    match_status: str = "POI_ONLY",
    search_radius: float = DEFAULT_POI_RADIUS,
) -> ScoredPoi:
    """Compute S_final = (P × h × U) × (D × w) × C for a single POI.

    Args:
        poi: Target POI.
        all_pois: All POIs near this DP (for uniqueness calculation).
        weather: WeatherCondition enum value.
        is_open_status: "OPEN", "CLOSED", or "UNKNOWN".
        match_status: "MATCHED", "POI_ONLY", or "VISION_ONLY".
        search_radius: Adaptive search radius (MD) used during POI collection.

    Returns:
        ScoredPoi with full breakdown.
    """
    p_h = compute_p_h(poi, is_open_status)
    d_w = compute_d_w(poi.distance, weather, search_radius)
    u = compute_uniqueness(poi, all_pois)
    c = CROSS_VALIDATION_COEFFICIENT.get(match_status, 1.0)
    s_final = (p_h * u) * d_w * c

    return ScoredPoi(
        poi=poi,
        p_h=p_h,
        d_w=d_w,
        u=u,
        c=c,
        s_final=s_final,
    )


def rank_pois(
    pois: list[PoiResult],
    weather: str = "CLEAR",
    is_open_statuses: dict[str, str] | None = None,
    match_statuses: dict[str, str] | None = None,
    search_radius: float = DEFAULT_POI_RADIUS,
) -> list[ScoredPoi]:
    """Score and rank all POIs for a single DP.

    Args:
        pois: POI list from poi_service.
        weather: WeatherCondition enum value.
        is_open_statuses: {place_name -> "OPEN"|"CLOSED"|"UNKNOWN"}, optional.
        match_statuses: {place_name -> "MATCHED"|"POI_ONLY"|"VISION_ONLY"}, optional.
        search_radius: Adaptive search radius (MD) used during POI collection.

    Returns:
        List of ScoredPoi sorted by s_final descending.
    """
    if not pois:
        return []

    open_map = is_open_statuses or {}
    match_map = match_statuses or {}

    scored = [
        score_poi(
            poi=poi,
            all_pois=pois,
            weather=weather,
            is_open_status=open_map.get(
                poi_identity_key(poi),
                open_map.get(poi.place_name, "UNKNOWN"),
            ),
            match_status=match_map.get(poi.place_name, "POI_ONLY"),
            search_radius=search_radius,
        )
        for poi in pois
    ]

    scored.sort(key=lambda s: s.s_final, reverse=True)
    return scored


def select_landmark(
    pois: list[PoiResult],
    weather: str = "CLEAR",
    is_open_statuses: dict[str, str] | None = None,
    match_statuses: dict[str, str] | None = None,
    search_radius: float = DEFAULT_POI_RADIUS,
) -> ScoredPoi | None:
    """Select the best landmark for a DP.

    Args:
        pois: POI list from poi_service.
        weather: WeatherCondition enum value.
        is_open_statuses: {place_name -> "OPEN"|"CLOSED"|"UNKNOWN"}, optional.
        match_statuses: {place_name -> "MATCHED"|"POI_ONLY"|"VISION_ONLY"}, optional.
        search_radius: Adaptive search radius (MD) used during POI collection.

    Returns:
        Best ScoredPoi, or None if no POIs.
    """
    ranked = rank_pois(pois, weather, is_open_statuses, match_statuses, search_radius)
    return ranked[0] if ranked else None
