"""Vision Service — Analyze panorama images via OpenAI Vision API.

Recognizes business signs, describes environment features, and verifies
turnType facilities (crosswalk, stairs, etc.) for cross-validation.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from io import BytesIO
from typing import Any

import httpx
from fastapi import HTTPException

from config import settings
from constants import FACILITY_KOREAN_NAMES, FACILITY_TURN_TYPES
from schemas import (
    VisionDpResult,
    VisionEnvironmentFeature,
    VisionFacilityResult,
    VisionShotResult,
    VisionSignResult,
)

logger = logging.getLogger(__name__)

OPENAI_VISION_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o"
MAX_IMAGE_PX = 1024
REQUEST_TIMEOUT = 30.0
MAX_RETRIES = 3

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_COMBINED_SYSTEM_PROMPT = (
    "You are a Korean street analysis system for pedestrian navigation. "
    "Analyze the provided street-level panorama image and extract:\n"
    "1. All visible business signs (간판) with exact names\n"
    "2. Notable environment features (building colors, walls, trees, etc.)\n\n"
    "Rules:\n"
    "- Extract business names exactly as written — do not guess\n"
    "- Only report signs that are clearly readable\n"
    "- For environment features, focus on stable, distinctive elements\n"
    "- Do NOT describe people, vehicles, or temporary objects\n"
    "- Use concise Korean for descriptions (max 10 characters)\n"
    "- Respond in JSON format"
)

_COMBINED_USER_TEMPLATE = (
    "Identify all visible business signs and notable environment features "
    "in this street-level panorama image.\n"
    "Direction context: this image is facing {direction} (pan={pan}°) "
    "from the walking route."
)

_FACILITY_SYSTEM_PROMPT = (
    "You are a pedestrian infrastructure detection system. "
    "Check if the specified facility is visible in the provided "
    "street-level panorama image.\n\n"
    "Rules:\n"
    "- Look specifically for the requested facility type\n"
    "- Report whether it is clearly visible, partially visible, or not visible\n"
    "- If visible, describe its approximate location in the image\n"
    "- Respond in JSON format"
)

_FACILITY_USER_TEMPLATE = (
    "Check if a {facility_type} is visible in this street-level panorama image.\n"
    "Expected facility: {facility_korean} (turnType={turn_type})\n"
    "Direction context: this image is facing {direction} (pan={pan}°) "
    "from the walking route."
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resize_image_base64(image_base64: str) -> str:
    """Resize image to MAX_IMAGE_PX if larger, return base64 string.

    Args:
        image_base64: base64-encoded image data.

    Returns:
        Possibly resized base64-encoded image data.
    """
    try:
        from PIL import Image

        raw = base64.b64decode(image_base64)
        img = Image.open(BytesIO(raw))
        w, h = img.size
        if max(w, h) <= MAX_IMAGE_PX:
            return image_base64
        scale = MAX_IMAGE_PX / max(w, h)
        new_size = (int(w * scale), int(h * scale))
        img = img.resize(new_size, Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        return image_base64


async def _call_openai_vision(
    client: httpx.AsyncClient,
    system_prompt: str,
    user_prompt: str,
    image_base64: str,
) -> dict[str, Any]:
    """Call OpenAI Vision API with retry and backoff.

    Args:
        client: httpx async client.
        system_prompt: system role content.
        user_prompt: user role text content.
        image_base64: base64-encoded image.

    Returns:
        Parsed JSON dict from the model response.
    """
    if not settings.openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured")

    image_base64 = _resize_image_base64(image_base64)

    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}",
                        },
                    },
                ],
            },
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 1000,
        "temperature": 0.1,
    }

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    backoff = 1.0
    for attempt in range(MAX_RETRIES):
        try:
            resp = await client.post(
                OPENAI_VISION_URL,
                json=payload,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code == 429:
                logger.warning("OpenAI rate limit hit, retrying in %.1fs", backoff)
                await asyncio.sleep(backoff)
                backoff *= 2
                continue
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except httpx.TimeoutException:
            logger.warning("OpenAI Vision timeout (attempt %d/%d)", attempt + 1, MAX_RETRIES)
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(backoff)
                backoff *= 2
                continue
            logger.error("OpenAI Vision failed after %d retries", MAX_RETRIES)
            return {}
        except (json.JSONDecodeError, KeyError, IndexError) as exc:
            logger.warning("Invalid OpenAI Vision response: %s", exc)
            return {}
        except httpx.HTTPStatusError as exc:
            logger.error("OpenAI Vision HTTP error: %s", exc)
            return {}

    return {}


def _parse_signs(raw: dict[str, Any]) -> list[VisionSignResult]:
    """Parse sign recognition results from Vision API response.

    Args:
        raw: parsed JSON response dict.

    Returns:
        List of VisionSignResult (only high/medium confidence).
    """
    signs: list[VisionSignResult] = []
    for item in raw.get("signs", []):
        confidence = item.get("confidence", "low")
        if confidence in ("high", "medium"):
            signs.append(
                VisionSignResult(
                    name=item.get("name", ""),
                    position_in_image=item.get("position_in_image", "center"),
                    confidence=confidence,
                )
            )
    return signs


def _parse_environment(raw: dict[str, Any]) -> list[VisionEnvironmentFeature]:
    """Parse environment features from Vision API response.

    Args:
        raw: parsed JSON response dict.

    Returns:
        List of VisionEnvironmentFeature.
    """
    features: list[VisionEnvironmentFeature] = []
    for item in raw.get("environment", raw.get("features", [])):
        features.append(
            VisionEnvironmentFeature(
                description=item.get("description", ""),
                position_in_image=item.get("position_in_image", "center"),
                feature_type=item.get("type", item.get("feature_type", "other")),
            )
        )
    return features


def _parse_facility(raw: dict[str, Any]) -> VisionFacilityResult:
    """Parse facility verification result from Vision API response.

    Args:
        raw: parsed JSON response dict.

    Returns:
        VisionFacilityResult.
    """
    return VisionFacilityResult(
        facility_type=raw.get("facility_type", ""),
        visible=raw.get("visible", False),
        visibility=raw.get("visibility", "not_visible"),
        position_in_image=raw.get("position_in_image"),
        description=raw.get("description"),
    )


# ---------------------------------------------------------------------------
# Per-shot analysis
# ---------------------------------------------------------------------------

async def _analyze_shot(
    client: httpx.AsyncClient,
    direction: str,
    pan: float,
    is_primary: bool,
    image_base64: str,
    turn_type: int | None,
    dp_type: str,
) -> VisionShotResult:
    """Analyze a single panorama shot (combined sign + environment, optional facility).

    Args:
        client: httpx async client.
        direction: shot direction label (front/left/right).
        pan: pan angle in degrees.
        is_primary: whether this is the primary shot.
        image_base64: base64-encoded panorama image.
        turn_type: Tmap turnType (None for VIRTUAL).
        dp_type: DP type string.

    Returns:
        VisionShotResult with signs, environment, and optional facility.
    """
    user_prompt = _COMBINED_USER_TEMPLATE.format(direction=direction, pan=pan)
    combined_result = await _call_openai_vision(
        client, _COMBINED_SYSTEM_PROMPT, user_prompt, image_base64
    )

    signs = _parse_signs(combined_result)
    environment = _parse_environment(combined_result)

    facility: VisionFacilityResult | None = None
    if turn_type is not None and turn_type in FACILITY_TURN_TYPES:
        facility_type = FACILITY_TURN_TYPES[turn_type]
        facility_korean = FACILITY_KOREAN_NAMES.get(facility_type, facility_type)
        facility_user = _FACILITY_USER_TEMPLATE.format(
            facility_type=facility_type,
            facility_korean=facility_korean,
            turn_type=turn_type,
            direction=direction,
            pan=pan,
        )
        facility_raw = await _call_openai_vision(
            client, _FACILITY_SYSTEM_PROMPT, facility_user, image_base64
        )
        if facility_raw:
            facility = _parse_facility(facility_raw)

    return VisionShotResult(
        direction=direction,
        pan=pan,
        is_primary=is_primary,
        signs=signs,
        environment=environment,
        facility=facility,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def analyze_panorama_images(
    dp_index: int,
    dp_type: str,
    turn_type: int | None,
    shots: list[dict],
) -> VisionDpResult:
    """Analyze panorama images for a single DP.

    Args:
        dp_index: DP position in route.
        dp_type: DP type (DIRECTION_CHANGE, CROSSWALK, etc.).
        turn_type: Tmap turnType code (None for VIRTUAL).
        shots: List of shot dicts with keys:
            direction (str), pan (float), is_primary (bool), image_base64 (str).

    Returns:
        VisionDpResult with signs, environment, and facility results per shot.
    """
    async with httpx.AsyncClient() as client:
        tasks = [
            _analyze_shot(
                client=client,
                direction=shot["direction"],
                pan=shot["pan"],
                is_primary=shot["is_primary"],
                image_base64=shot["image_base64"],
                turn_type=turn_type,
                dp_type=dp_type,
            )
            for shot in shots
        ]
        shot_results = await asyncio.gather(*tasks)

    return VisionDpResult(
        dp_index=dp_index,
        dp_type=dp_type,
        shots=list(shot_results),
    )


async def analyze_all_dps(
    dps: list[dict],
) -> list[VisionDpResult]:
    """Batch analyze all DPs. Runs concurrently with asyncio.gather.

    Args:
        dps: List of DP dicts with keys:
            dp_index (int), dp_type (str), turn_type (int | None),
            shots (list[dict]) — each shot has direction, pan, is_primary, image_base64.

    Returns:
        List of VisionDpResult, one per DP.
    """
    tasks = [
        analyze_panorama_images(
            dp_index=dp["dp_index"],
            dp_type=dp["dp_type"],
            turn_type=dp.get("turn_type"),
            shots=dp["shots"],
        )
        for dp in dps
    ]
    return list(await asyncio.gather(*tasks))
