"""Pydantic v2 models — Python ↔ Spring Boot interface contract."""

from __future__ import annotations

from typing import Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from vision_schemas import VisionAnalysisData


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
    primary_audio: Optional[str] = None  # base64-encoded mp3 for primary guidance
    pre_alert_audio: Optional[str] = None  # base64-encoded mp3 for pre_alert guidance


# ---------------------------------------------------------------------------
# SelectedLandmark
# ---------------------------------------------------------------------------

class SelectedLandmark(BaseModel):
    name: str
    category_code: str
    position: str  # LEFT | RIGHT | FRONT
    distance: float
    score: float
    match_status: str  # Production currently emits POI_ONLY; MATCHED/VISION_ONLY are reserved for future Vision integration.
    is_open: bool = True
    location: Optional[Location] = None  # POI coordinates (from Kakao API)
    appearance: Optional[str] = None  # Reserved for dev fixtures or future Vision integration; production pipeline does not generate it.
    visual_context: Optional[VisionAnalysisData] = None
    position_confirm: Optional[str] = None  # Deterministic answer for Mode B position-confirm questions


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
    pan_override: Optional[float] = None


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
    tmap_description: Optional[str] = Field(
        default=None,
        exclude=True,
        description="Original Tmap description. Internal only, excluded from API response.",
    )


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
    """대화형 답변 요청.

    Spring Boot가 raw JSON을 그대로 전달하므로 RN의 camelCase 키를
    그대로 받기 위해 alias 사용. populate_by_name=True 덕분에 내부 코드/테스트는
    snake_case 키워드로 그대로 생성 가능.
    """
    model_config = ConfigDict(populate_by_name=True)

    question: str
    route_id: str = Field(alias="routeId")
    current_dp_id: Optional[str] = Field(default=None, alias="currentDpId")
    completed_dp_ids: Optional[list[str]] = Field(default=None, alias="completedDpIds")


class ConversationResponse(BaseModel):
    answer: str
    show_panorama: bool = False
    target_dp_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Common API wrapper
# ---------------------------------------------------------------------------

class ApiResponse(BaseModel):
    status: str = "SUCCESS"  # SUCCESS | ERROR
    data: Optional[
        Union[
            dict,
            list,
            RouteResponse,
            DeviationResponse,
            ConversationResponse,
            VisionAnalysisData,
        ]
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
