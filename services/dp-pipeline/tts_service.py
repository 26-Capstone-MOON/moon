"""Google Cloud Text-to-Speech service using REST API with API key."""

from __future__ import annotations

import base64
from typing import Optional

import httpx

from config import settings

_TTS_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"


async def synthesize(text: str) -> Optional[str]:
    """Convert *text* to speech via Google Cloud TTS.

    Returns base64-encoded mp3 audio string, or ``None`` on failure.
    """
    api_key = settings.google_tts_api_key
    if not api_key:
        print("[TTS] GOOGLE_TTS_API_KEY not set, skipping synthesis")
        return None

    payload = {
        "input": {"text": text},
        "voice": {
            "languageCode": "ko-KR",
            "name": "ko-KR-Wavenet-A",
        },
        "audioConfig": {
            "audioEncoding": "MP3",
            "speakingRate": 1.0,
            "pitch": 0.0,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _TTS_URL,
                params={"key": api_key},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            audio_content = data.get("audioContent")
            if audio_content:
                return audio_content  # already base64 from Google
            print("[TTS] No audioContent in response")
            return None
    except Exception as e:
        print(f"[TTS] Synthesis failed for '{text[:30]}...': {e}")
        return None


async def synthesize_guidance(primary: str, pre_alert: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
    """Synthesize both primary and pre_alert texts.

    Returns ``(primary_audio_b64, pre_alert_audio_b64)``.
    """
    primary_audio = await synthesize(primary)
    pre_alert_audio = None
    if pre_alert:
        pre_alert_audio = await synthesize(pre_alert)
    return primary_audio, pre_alert_audio
