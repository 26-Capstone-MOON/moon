from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class VisionAnalysisStatus(str, Enum):
    ANALYZED = "ANALYZED"
    NO_IMAGE = "NO_IMAGE"
    CAPTURE_FAILED = "CAPTURE_FAILED"
    MODEL_FAILED = "MODEL_FAILED"
    UNSUPPORTED = "UNSUPPORTED"
    VISION_DISABLED = "VISION_DISABLED"


class VisionDirection(str, Enum):
    FRONT = "FRONT"
    LEFT = "LEFT"
    RIGHT = "RIGHT"


class VisionPurpose(str, Enum):
    SALIENCE = "SALIENCE"
    APPEARANCE = "APPEARANCE"
    SURROUNDING = "SURROUNDING"


class VisionCueType(str, Enum):
    SIGN = "SIGN"
    COLOR = "COLOR"
    CROSSWALK = "CROSSWALK"
    STAIRS = "STAIRS"
    FENCE = "FENCE"
    BUILDING = "BUILDING"
    ROAD_FEATURE = "ROAD_FEATURE"


class VisionSelectedLandmark(BaseModel):
    name: Optional[str] = None
    category_code: Optional[str] = None
    position: Optional[VisionDirection] = None


class VisionAnalyzeRequest(BaseModel):
    route_id: str
    dp_id: str
    direction: VisionDirection
    image_base64: Optional[str] = None
    selected_landmark: Optional[VisionSelectedLandmark] = None
    analysis_purpose: VisionPurpose = VisionPurpose.SURROUNDING

    @field_validator("route_id", "dp_id")
    @classmethod
    def non_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


class VisionCue(BaseModel):
    type: VisionCueType
    description: str
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("description")
    @classmethod
    def cue_description_non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("description must not be blank")
        return value


class LandmarkVerification(BaseModel):
    landmark_name: Optional[str] = None
    visible: bool
    confidence: float = Field(ge=0.0, le=1.0)


class VisionAnalysisData(BaseModel):
    analysis_status: VisionAnalysisStatus
    candidate_name: Optional[str] = None
    candidate_type: Optional[str] = None
    direction: Optional[VisionDirection] = None
    purposes: list[VisionPurpose] = Field(default_factory=list)
    color_distinctiveness: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    text_sign_ratio: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    v_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    appearance_description: Optional[str] = None
    scene_description: Optional[str] = None
    visual_cues: list[VisionCue] = Field(default_factory=list, max_length=3)
    landmark_verification: Optional[LandmarkVerification] = None
    has_crosswalk: bool = False
    has_stairs: bool = False
    source: Optional[str] = None
    cache_key: Optional[str] = None
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def empty_vision_result(status: VisionAnalysisStatus) -> VisionAnalysisData:
    return VisionAnalysisData(
        analysis_status=status,
        scene_description=None,
        visual_cues=[],
        landmark_verification=None,
        has_crosswalk=False,
        has_stairs=False,
    )
