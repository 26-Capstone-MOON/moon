"""Pydantic v2 models — Python ↔ Spring Boot interface contract."""

from __future__ import annotations

from typing import Optional, Union

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared value objects
# ---------------------------------------------------------------------------

class Location(BaseModel):
    latitude: float
    longitude: float


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class RouteRequest(BaseModel):
    origin_lat: float
    origin_lng: float
    dest_lat: float
    dest_lng: float
    dest_name: str = ""


# ---------------------------------------------------------------------------
# Guidance
# ---------------------------------------------------------------------------

class Guidance(BaseModel):
    primary: str
    pre_alert: Optional[str] = None
    action: Optional[str] = None  # GuidanceAction enum value


# ---------------------------------------------------------------------------
# SelectedLandmark
# ---------------------------------------------------------------------------

class SelectedLandmark(BaseModel):
    name: str
    category_code: str
    position: str  # LEFT | RIGHT | FRONT
    distance: float
    score: float
    match_status: str  # MATCHED | POI_ONLY | VISION_ONLY
    is_open: bool = True
    location: Optional[Location] = None  # POI coordinates (from Kakao API)


# ---------------------------------------------------------------------------
# PanoramaRequest
# ---------------------------------------------------------------------------

class PanoramaDirection(BaseModel):
    pan: float
    label: str  # FRONT | LEFT | RIGHT
    is_primary: bool


class PanoramaRequest(BaseModel):
    location: Location
    directions: list[PanoramaDirection]


# ---------------------------------------------------------------------------
# DecisionPoint
# ---------------------------------------------------------------------------

class DecisionPoint(BaseModel):
    dp_id: str
    dp_type: str  # DpType enum value
    turn_type: Optional[int] = None
    location: Location
    bearing: Optional[float] = None
    distance_from_start: float = 0.0
    guidance: Guidance
    selected_landmark: Optional[SelectedLandmark] = None
    panorama_request: Optional[PanoramaRequest] = None


# ---------------------------------------------------------------------------
# RouteResponse
# ---------------------------------------------------------------------------

class RouteResponse(BaseModel):
    route_id: str
    origin: Location
    destination: Location
    dest_name: str = ""
    total_distance: float = Field(description="Total distance in meters")
    total_time: float = Field(description="Estimated time in seconds")
    decision_points: list[DecisionPoint]
    route_line_string: list[Location] = Field(
        default_factory=list,
        description="Ordered list of coordinates forming the route polyline",
    )
    weather: str = "CLEAR"  # WeatherCondition enum value
    is_rerouted: bool = False
    previous_route_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Deviation models (used by deviation service, defined here for sharing)
# ---------------------------------------------------------------------------

class DeviationRequest(BaseModel):
    route_id: str
    current_location: Location
    route_line_string: list[Location]
    current_dp_id: str
    timestamp: float  # epoch seconds


class DeviationResponse(BaseModel):
    navigation_state: str  # NavigationState enum value
    current_dp_id: str
    distance_to_dp: float
    trigger: Optional[str] = None
    guidance: Optional[Guidance] = None
    progress: Optional["Progress"] = None


class Progress(BaseModel):
    completed_dps: list[str]
    current_dp_id: str
    remaining_dps: list[str]
    distance_remaining: float
    time_remaining: float


# ---------------------------------------------------------------------------
# Conversation models
# ---------------------------------------------------------------------------

class ConversationRequest(BaseModel):
    question: str
    route_id: str
    current_dp_id: Optional[str] = None


class ConversationResponse(BaseModel):
    answer: str


# ---------------------------------------------------------------------------
# Cross-validation
# ---------------------------------------------------------------------------

class CrossValidationResult(BaseModel):
    poi_name: str
    vision_name: Optional[str] = None
    match_status: str  # MATCHED | POI_ONLY | VISION_ONLY
    c_coefficient: float  # 1.5 | 1.2 | 1.0
    category_group_code: str


# ---------------------------------------------------------------------------
# Vision models
# ---------------------------------------------------------------------------

class VisionSignResult(BaseModel):
    name: str
    position_in_image: str  # left | center | right
    confidence: str  # high | medium | low


class VisionEnvironmentFeature(BaseModel):
    description: str  # Korean, max 10 chars (e.g., "회색 건물")
    position_in_image: str  # left | center | right
    feature_type: str  # building | wall | fence | tree | bench | sign_structure | gate | other


class VisionFacilityResult(BaseModel):
    facility_type: str  # crosswalk | stairs | overpass | underpass | elevator
    visible: bool
    visibility: str  # clear | partial | not_visible
    position_in_image: Optional[str] = None
    description: Optional[str] = None


class VisionShotResult(BaseModel):
    direction: str  # front | left | right
    pan: float
    is_primary: bool
    signs: list[VisionSignResult] = Field(default_factory=list)
    environment: list[VisionEnvironmentFeature] = Field(default_factory=list)
    facility: Optional[VisionFacilityResult] = None


class VisionDpResult(BaseModel):
    dp_index: int
    dp_type: str
    shots: list[VisionShotResult] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Common API wrapper
# ---------------------------------------------------------------------------

class ApiResponse(BaseModel):
    status: str = "SUCCESS"  # SUCCESS | ERROR
    data: Optional[
        Union[dict, list, RouteResponse, DeviationResponse, ConversationResponse]
    ] = None
    error: Optional[dict] = None


# ---------------------------------------------------------------------------
# GPS / Deviation detection models
# ---------------------------------------------------------------------------

class GpsReading(BaseModel):
    lat: float
    lng: float
    timestamp: float  # Unix epoch seconds


class DeviationResult(BaseModel):
    state: str  # DeviationState value
    distance_to_route_m: float
    duration_s: float = 0.0
    trend: Optional[str] = None  # ContinuityTrend value
    message: Optional[str] = None
    should_reroute: bool = False
    gps_error: bool = False


# ---------------------------------------------------------------------------
# Rerouting models
# ---------------------------------------------------------------------------

class RerouteRequest(BaseModel):
    current_lat: float
    current_lng: float
    dest_lat: float
    dest_lng: float
    dest_name: str = ""
    previous_route_id: Optional[str] = None


class RerouteResponse(BaseModel):
    success: bool
    route_response: Optional[RouteResponse] = None
    reused_dp_count: int = 0
    error_message: Optional[str] = None
