"""Pipeline constants: turnType mapping, scoring coefficients, thresholds."""

from enum import Enum

# ---------------------------------------------------------------------------
# turnType → DpType mapping
# ---------------------------------------------------------------------------

TURN_TYPE_TO_DP_TYPE: dict[int, str] = {
    # Direction change (12~19)
    12: "DIRECTION_CHANGE",
    13: "DIRECTION_CHANGE",
    14: "DIRECTION_CHANGE",
    15: "DIRECTION_CHANGE",
    16: "DIRECTION_CHANGE",
    17: "DIRECTION_CHANGE",
    18: "DIRECTION_CHANGE",
    19: "DIRECTION_CHANGE",
    # Crosswalk (211~217)
    211: "CROSSWALK",
    212: "CROSSWALK",
    213: "CROSSWALK",
    214: "CROSSWALK",
    215: "CROSSWALK",
    216: "CROSSWALK",
    217: "CROSSWALK",
    # Vertical move / infrastructure
    125: "VERTICAL_MOVE",  # overpass
    126: "VERTICAL_MOVE",  # underpass
    127: "VERTICAL_MOVE",  # stairs
    128: "VERTICAL_MOVE",  # stairs
    129: "VERTICAL_MOVE",  # stairs
    218: "VERTICAL_MOVE",  # elevator
    # Origin / destination
    200: "DEPARTURE",
    201: "ARRIVAL",
}

# turnTypes to exclude (straight segments, no guidance)
EXCLUDED_TURN_TYPES: set[int] = {1, 2, 3, 4, 5, 6, 7, 11}

# ---------------------------------------------------------------------------
# turnType → GuidanceAction mapping
# ---------------------------------------------------------------------------

TURN_TYPE_TO_ACTION: dict[int, str] = {
    12: "LEFT_TURN",
    13: "RIGHT_TURN",
    14: "LEFT_TURN",
    15: "RIGHT_TURN",
    16: "LEFT_TURN",
    17: "LEFT_TURN",
    18: "RIGHT_TURN",
    19: "RIGHT_TURN",
    125: "OVERPASS",
    126: "UNDERPASS",
    127: "STAIRS_UP",
    128: "STAIRS_DOWN",
    129: "STAIRS_UP",
    211: "CROSSWALK",
    212: "CROSSWALK",
    213: "CROSSWALK",
    214: "CROSSWALK",
    215: "CROSSWALK",
    216: "CROSSWALK",
    217: "CROSSWALK",
    218: "ELEVATOR",
}

# ---------------------------------------------------------------------------
# Panorama: turnType → isPrimary direction
# ---------------------------------------------------------------------------

LEFT_PRIMARY_TURN_TYPES: set[int] = {12, 16, 17, 212, 214, 215}
RIGHT_PRIMARY_TURN_TYPES: set[int] = {13, 18, 19, 213, 216, 217}

# ---------------------------------------------------------------------------
# Facility type mapping (turnType → facility name for Vision verification)
# ---------------------------------------------------------------------------

FACILITY_TURN_TYPES: dict[int, str] = {
    211: "crosswalk",
    212: "crosswalk",
    213: "crosswalk",
    214: "crosswalk",
    215: "crosswalk",
    216: "crosswalk",
    217: "crosswalk",
    125: "overpass",
    126: "underpass",
    127: "stairs",
    128: "stairs",
    129: "stairs",
    218: "elevator",
}

FACILITY_KOREAN_NAMES: dict[str, str] = {
    "crosswalk": "횡단보도",
    "overpass": "육교",
    "underpass": "지하보도",
    "stairs": "계단",
    "elevator": "엘리베이터",
}

# ---------------------------------------------------------------------------
# P(h) — Category awareness value by Kakao category_group_code
# ---------------------------------------------------------------------------

CATEGORY_P_VALUES: dict[str, float] = {
    "MT1": 1.0,   # Large mart
    "PO3": 0.95,  # Public institution
    "BK9": 0.9,   # Bank
    "SC4": 0.85,  # School
    "SW8": 0.8,   # Subway station
    "OL7": 0.75,  # Gas station
    "CS2": 0.7,   # Convenience store
    "HP8": 0.65,  # Hospital
    "PM9": 0.6,   # Pharmacy
    "CT1": 0.55,  # Cultural facility
    "AT4": 0.5,   # Tourist attraction
    "CE7": 0.45,  # Cafe
    "FD6": 0.4,   # Restaurant
    "PS3": 0.35,  # Kindergarten
    "AG2": 0.35,  # Real estate
    "AC5": 0.3,   # Academy
    "AD5": 0.25,  # Accommodation
    "PK6": 0.2,   # Parking lot
}

DEFAULT_P_VALUE: float = 0.3

# ---------------------------------------------------------------------------
# isOpen adjustment (Google Places API)
# ---------------------------------------------------------------------------

IS_OPEN_COEFFICIENT: dict[str, float] = {
    "OPEN": 1.0,
    "CLOSED": 0.5,
    "UNKNOWN": 0.7,
}

# ---------------------------------------------------------------------------
# D(w) — Weather modifier (w_mod)
# ---------------------------------------------------------------------------


class WeatherCondition(str, Enum):
    CLEAR = "CLEAR"
    CLOUDY = "CLOUDY"
    RAIN = "RAIN"
    SNOW = "SNOW"
    FOG = "FOG"


WEATHER_W_MOD: dict[str, float] = {
    WeatherCondition.CLEAR: 1.0,
    WeatherCondition.CLOUDY: 0.85,
    WeatherCondition.RAIN: 0.6,
    WeatherCondition.SNOW: 0.5,
    WeatherCondition.FOG: 0.4,
}

# ---------------------------------------------------------------------------
# U — Uniqueness by same-category count within 100m
# ---------------------------------------------------------------------------

UNIQUENESS_SCORES: dict[int, float] = {
    1: 1.0,
    2: 0.7,
    3: 0.4,
}
UNIQUENESS_DEFAULT: float = 0.2  # 4+

# ---------------------------------------------------------------------------
# C_bonus — Cross-validation bonus
# ---------------------------------------------------------------------------

CROSS_VALIDATION_BONUS: dict[str, float] = {
    "MATCHED": 0.5,
    "POI_ONLY": 0.2,
    "VISION_ONLY": 0.0,
}

# ---------------------------------------------------------------------------
# Distance / threshold constants
# ---------------------------------------------------------------------------

MAX_SEARCH_RADIUS: float = 100.0          # MD for D(w) formula (meters)
DEFAULT_POI_RADIUS: float = 50.0          # initial POI search radius (meters)
POI_RADIUS_EXPAND_1: float = 75.0         # first expansion
POI_RADIUS_EXPAND_2: float = 100.0        # second expansion
POI_RADIUS_SHRINK: float = 30.0           # shrink when 10+ results
VIRTUAL_DP_THRESHOLD: float = 200.0       # insert virtual DP when gap > 200m
VIRTUAL_DP_MIN_SPACING: float = 100.0     # minimum spacing between virtual DPs
VIRTUAL_DP_CANDIDATE_INTERVAL: float = 30.0  # candidate generation interval (20~50m)

PRE_ALERT_DISTANCE: float = 30.0          # meters
ARRIVAL_DISTANCE: float = 10.0            # meters

# Deviation detection thresholds
DEVIATION_DISTANCE_THRESHOLD: float = 20.0   # meters
DEVIATION_SPEED_THRESHOLD: float = 15.0      # km/h
DEVIATION_WARNING_SECONDS: float = 3.0
DEVIATION_CONFIRMED_SECONDS: float = 5.0

# Deviation thresholds (aliased names matching deviation_detect.md spec)
DEVIATION_DISTANCE_THRESHOLD_M: float = 20.0
SPEED_THRESHOLD_KMH: float = 15.0
DEVIATION_WARNING_DURATION_S: float = 3.0
DEVIATION_CONFIRM_DURATION_S: float = 5.0
CONTINUITY_SAMPLE_COUNT: int = 3
GPS_UPDATE_INTERVAL_S: float = 1.0


# ---------------------------------------------------------------------------
# DeviationState — string constants
# ---------------------------------------------------------------------------

class DeviationState:
    NORMAL = "NORMAL"
    SUSPECTED = "SUSPECTED"
    WARNING = "WARNING"
    CONFIRMING = "CONFIRMING"
    DEVIATED = "DEVIATED"
    RETURNING = "RETURNING"


# ---------------------------------------------------------------------------
# ContinuityTrend — string constants
# ---------------------------------------------------------------------------

class ContinuityTrend:
    DIVERGING = "DIVERGING"
    CONVERGING = "CONVERGING"
    IRREGULAR = "IRREGULAR"


# ---------------------------------------------------------------------------
# Deviation guidance messages (Korean)
# ---------------------------------------------------------------------------

DEVIATION_MSG_WARNING: str = "경로를 벗어난 것 같아요."
DEVIATION_MSG_RETURNING: str = "다시 돌아오고 있어요. 잘 하고 있어요."
DEVIATION_MSG_REROUTING: str = "경로를 다시 찾고 있어요. 잠시만요."
DEVIATION_MSG_REROUTE_DONE: str = "새 경로를 찾았어요."
