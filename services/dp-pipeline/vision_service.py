from __future__ import annotations

import base64
import hashlib
import json
import logging
from typing import Any

import httpx

from config import settings
from vision_prompt import VISION_SYSTEM_PROMPT, build_vision_user_prompt
from vision_schemas import (
    LandmarkVerification,
    VisionAnalysisData,
    VisionAnalysisStatus,
    VisionAnalyzeRequest,
    VisionCue,
    VisionPurpose,
    empty_vision_result,
)

logger = logging.getLogger(__name__)

_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_MAX_IMAGE_BYTES = 1_500_000
_TIMEOUT_S = 20.0
_VISION_CACHE: dict[tuple[str, str, str], VisionAnalysisData] = {}


def _decode_data_url(image_base64: str | None) -> tuple[str | None, bytes | None]:
    if not image_base64:
        return None, None
    if not image_base64.startswith("data:image/"):
        raise ValueError("image_base64 must be a data:image URL")
    header, sep, encoded = image_base64.partition(",")
    if not sep or ";base64" not in header:
        raise ValueError("image_base64 must be base64 encoded")
    mime = header.removeprefix("data:").split(";")[0]
    data = base64.b64decode(encoded, validate=True)
    return mime, data


def _sanitize_model_json(raw: dict[str, Any], landmark_name: str | None) -> VisionAnalysisData:
    cues: list[VisionCue] = []
    for item in raw.get("visual_cues") or []:
        try:
            cues.append(VisionCue.model_validate(item))
        except Exception:
            continue
        if len(cues) >= 3:
            break

    verification = None
    if landmark_name and isinstance(raw.get("landmark_verification"), dict):
        try:
            verification = LandmarkVerification.model_validate(
                raw["landmark_verification"]
            )
        except Exception:
            verification = None

    scene = raw.get("scene_description")
    if scene is not None:
        scene = str(scene).strip()[:160] or None

    purposes: list[VisionPurpose] = []
    for purpose in raw.get("purposes") or []:
        try:
            purposes.append(VisionPurpose(str(purpose)))
        except Exception:
            continue

    return VisionAnalysisData(
        analysis_status=VisionAnalysisStatus.ANALYZED,
        candidate_name=(str(raw.get("candidate_name")).strip() or None) if raw.get("candidate_name") else landmark_name,
        candidate_type=(str(raw.get("candidate_type")).strip() or None) if raw.get("candidate_type") else None,
        purposes=purposes,
        color_distinctiveness=raw.get("color_distinctiveness"),
        text_sign_ratio=raw.get("text_sign_ratio"),
        v_score=raw.get("v_score"),
        appearance_description=(str(raw.get("appearance_description")).strip()[:160] or None) if raw.get("appearance_description") else None,
        scene_description=scene,
        visual_cues=cues,
        landmark_verification=verification,
        has_crosswalk=bool(raw.get("has_crosswalk", False)),
        has_stairs=bool(raw.get("has_stairs", False)),
    )


async def analyze_panorama(request: VisionAnalyzeRequest) -> VisionAnalysisData:
    if not settings.vision_enabled:
        return empty_vision_result(VisionAnalysisStatus.VISION_DISABLED)
    if not settings.openai_api_key:
        return empty_vision_result(VisionAnalysisStatus.VISION_DISABLED)

    try:
        mime, image_bytes = _decode_data_url(request.image_base64)
    except Exception as exc:
        logger.warning("Vision image decode failed route=%s dp=%s: %s", request.route_id, request.dp_id, exc)
        return empty_vision_result(VisionAnalysisStatus.CAPTURE_FAILED)

    if image_bytes is None or mime is None:
        return empty_vision_result(VisionAnalysisStatus.NO_IMAGE)
    if len(image_bytes) > _MAX_IMAGE_BYTES:
        logger.warning(
            "Vision image too large route=%s dp=%s bytes=%d",
            request.route_id,
            request.dp_id,
            len(image_bytes),
        )
        return empty_vision_result(VisionAnalysisStatus.CAPTURE_FAILED)

    cache_key = (request.route_id, request.dp_id, request.direction.value)
    cached = _VISION_CACHE.get(cache_key)
    if cached is not None:
        return cached

    image_hash = hashlib.sha256(image_bytes).hexdigest()[:16]
    logger.info(
        "Vision analyze request route=%s dp=%s direction=%s mime=%s bytes=%d sha256=%s",
        request.route_id,
        request.dp_id,
        request.direction.value,
        mime,
        len(image_bytes),
        image_hash,
    )

    landmark_name = request.selected_landmark.name if request.selected_landmark else None
    payload = {
        "model": settings.vision_model,
        "messages": [
            {"role": "system", "content": VISION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": build_vision_user_prompt(
                            request.route_id,
                            request.dp_id,
                            request.direction.value,
                            landmark_name,
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": request.image_base64},
                    },
                ],
            },
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.0,
        "max_tokens": 450,
    }

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
                resp = await client.post(
                    _OPENAI_URL,
                    headers={
                        "Authorization": f"Bearer {settings.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                result = _sanitize_model_json(json.loads(content), landmark_name)
                result = result.model_copy(update={
                    "direction": request.direction,
                    "purposes": result.purposes or [request.analysis_purpose],
                })
                _VISION_CACHE[cache_key] = result
                return result
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Vision model call failed route=%s dp=%s attempt=%d: %s",
                request.route_id,
                request.dp_id,
                attempt + 1,
                exc,
            )

    logger.error("Vision analysis failed route=%s dp=%s: %s", request.route_id, request.dp_id, last_error)
    return empty_vision_result(VisionAnalysisStatus.MODEL_FAILED)
