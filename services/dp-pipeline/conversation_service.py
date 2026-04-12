"""Conversation Service — Mode B conversational guidance via OpenAI.

Answers user questions about the current route using cached route context
(decision points, landmarks, guidance text).

Tone rules match guidance.md: no distance numbers, friendly conversational style,
landmark-based descriptions.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from config import settings
from schemas import ConversationRequest, ConversationResponse, RouteResponse

logger = logging.getLogger(__name__)

_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_MODEL = "gpt-4o"
_TIMEOUT_S = 15.0

# ---------------------------------------------------------------------------
# Weather Korean mapping
# ---------------------------------------------------------------------------

_WEATHER_KR: dict[str, str] = {
    "CLEAR": "맑음",
    "CLOUDY": "흐림",
    "RAIN": "비",
    "SNOW": "눈",
    "FOG": "안개",
}

# ---------------------------------------------------------------------------
# Position Korean mapping
# ---------------------------------------------------------------------------

_POSITION_KR: dict[str, str] = {
    "LEFT": "왼쪽",
    "RIGHT": "오른쪽",
    "FRONT": "전방",
}


def _progress_label(completed: int, total: int) -> str:
    """Convert progress ratio to natural language."""
    if total <= 0:
        return ""
    ratio = completed / total
    if ratio <= 0.0:
        return "막 출발했어요"
    if ratio < 0.3:
        return "초반이에요"
    if ratio < 0.6:
        return "거의 중간쯤이에요"
    if ratio < 0.85:
        return "꽤 왔어요"
    return "거의 다 왔어요"


def _dp_summary(dp, include_landmark: bool = True) -> str:
    """Build a concise one-line summary of a DP for context."""
    parts: list[str] = []
    parts.append(dp.guidance.primary)
    if include_landmark and dp.selected_landmark:
        lm = dp.selected_landmark
        pos = _POSITION_KR.get(lm.position, "")
        parts.append(f"랜드마크: {lm.name} ({pos})")
    return " | ".join(parts)


def _build_route_context(
    route: RouteResponse,
    current_dp_id: Optional[str],
    completed_dp_ids: Optional[set[str]] = None,
) -> str:
    """Build structured route context for the system prompt.

    Args:
        route: Cached RouteResponse.
        current_dp_id: DP the user is currently near.
        completed_dp_ids: Set of dp_ids the user has already passed.

    Returns:
        Structured Korean context string (no distance numbers).
    """
    dps = route.decision_points
    total = len(dps)

    # Determine current DP index
    current_idx: int | None = None
    if current_dp_id:
        for i, dp in enumerate(dps):
            if dp.dp_id == current_dp_id:
                current_idx = i
                break

    # Build completed set — if not provided, derive from current index
    if completed_dp_ids is not None:
        completed = completed_dp_ids
    elif current_idx is not None:
        completed = {dps[j].dp_id for j in range(current_idx)}
    else:
        completed = set()

    completed_count = sum(1 for dp in dps if dp.dp_id in completed)
    weather_kr = _WEATHER_KR.get(route.weather, route.weather)

    lines: list[str] = []

    # --- Route summary ---
    lines.append("경로 요약:")
    lines.append(f"- 목적지: {route.dest_name or '목적지'}")
    lines.append(f"- 전체: {total}개 구간")
    lines.append(f"- 날씨: {weather_kr}")
    lines.append("")

    # --- Progress ---
    progress = _progress_label(completed_count, total)
    lines.append("진행 상황:")
    lines.append(f"- 완료: {completed_count}/{total} 구간 ({progress})")
    if current_idx is not None:
        lines.append(f"- 현재: {current_idx + 1}번째 구간")
    lines.append("")

    # --- Current DP ---
    if current_idx is not None:
        dp = dps[current_idx]
        lines.append("현재 구간:")
        lines.append(f"- 안내: {dp.guidance.primary}")
        if dp.selected_landmark:
            lm = dp.selected_landmark
            pos = _POSITION_KR.get(lm.position, "")
            lines.append(f"- 랜드마크: {lm.name} ({pos})")
        lines.append("")

    # --- Next DPs (max 2) ---
    start = (current_idx + 1) if current_idx is not None else 0
    upcoming = dps[start : start + 2]
    for j, dp in enumerate(upcoming):
        label = "다음 구간:" if j == 0 else "그 다음:"
        lines.append(label)
        lines.append(f"- 안내: {dp.guidance.primary}")
        if dp.guidance.pre_alert:
            lines.append(f"- 예고: {dp.guidance.pre_alert}")
        if dp.selected_landmark:
            lm = dp.selected_landmark
            pos = _POSITION_KR.get(lm.position, "")
            lines.append(f"- 랜드마크: {lm.name} ({pos})")
        lines.append("")

    # --- Completed DPs (brief) ---
    completed_dps = [dp for dp in dps if dp.dp_id in completed]
    if completed_dps:
        lines.append("이전 완료:")
        for dp in completed_dps:
            lm_name = dp.selected_landmark.name if dp.selected_landmark else ""
            if dp.dp_type == "DEPARTURE":
                lines.append("- 출발 (완료)")
            elif lm_name:
                lines.append(f"- {dp.guidance.primary} (완료)")
            else:
                lines.append(f"- {dp.dp_type}: {dp.guidance.primary} (완료)")

    return "\n".join(lines)


_SYSTEM_PROMPT_TEMPLATE = """\
너는 보행자 내비게이션 앱 Moon의 안내 도우미야.
사용자가 길 안내 중 궁금한 걸 물어보면 친근하게 대답해줘.

## 규칙 (반드시 지킬 것)
- 절대 거리를 숫자(m, 미터)로 말하지 마. "조금만 더 가면", "곧", "거의 다 왔어요" 사용
- "보이시죠?", "맞죠?" 같은 확인 질문 금지
- 랜드마크 이름과 위치(왼쪽/오른쪽)로 설명
- 2~3문장으로 짧고 따뜻하게
- 경로 정보에 있는 내용만 답변. 추측하지 마.

## 질문 유형별 답변

확인형 ("잘 가고 있어?", "맞는 길이야?"):
→ 현재 랜드마크로 확인 + 다음 예고
예: "네, 잘 가고 있어요! 오른쪽에 이디야커피가 보이면 맞는 길이에요. 조금만 더 가면 CU가 나올 거예요."

진행형 ("어디쯤이야?", "많이 남았어?"):
→ 진행 상황 + 최근 랜드마크 + 다음 예고
예: "지금 세 번째 구간이에요. 국민은행 지나셨으면 거의 중간쯤이에요! 다음은 올리브영에서 우회전이에요."

다음동작형 ("다음 뭐야?", "다음에 뭐 해?"):
→ 다음 DP의 랜드마크 + 동작
예: "곧 오른쪽에 올리브영이 보일 거예요. 올리브영을 끼고 우회전하세요."

기타: 경로 정보에서 찾아 랜드마크 기반으로 답변

## 경로 정보
{route_context}"""


async def chat(
    request: ConversationRequest,
    route: RouteResponse,
    completed_dp_ids: set[str] | None = None,
) -> ConversationResponse:
    """Answer a user question using route context via OpenAI Chat API.

    Args:
        request: User's question with route_id and optional current_dp_id.
        route: Cached RouteResponse for context.
        completed_dp_ids: Set of dp_ids the user has already passed.

    Returns:
        ConversationResponse with the assistant's answer.
    """
    route_context = _build_route_context(route, request.current_dp_id, completed_dp_ids)
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(route_context=route_context)

    payload = {
        "model": _MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.question},
        ],
        "temperature": 0.7,
        "max_tokens": 300,
    }

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
            data = resp.json()
            answer = data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.error("OpenAI API call failed: %s", exc)
        answer = "죄송해요, 지금 답변을 드리기 어렵습니다. 잠시 후 다시 시도해 주세요."

    return ConversationResponse(answer=answer)
