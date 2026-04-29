"""Conversation Service — Mode B conversational guidance via OpenAI.

Answers user questions about the current route using cached route context
(decision points, landmarks, guidance text).
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from config import settings
from schemas import ConversationRequest, ConversationResponse, DecisionPoint, RouteResponse

logger = logging.getLogger(__name__)

_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_MODEL = "gpt-4o"
_TIMEOUT_S = 15.0


def _build_route_context(route: RouteResponse, current_dp_id: Optional[str]) -> str:
    """Serialize route info into a compact context string for the system prompt."""
    lines: list[str] = []
    lines.append(f"경로 ID: {route.route_id}")
    lines.append(f"출발지: ({route.origin.latitude:.6f}, {route.origin.longitude:.6f})")
    lines.append(f"목적지: {route.dest_name or '목적지'} ({route.destination.latitude:.6f}, {route.destination.longitude:.6f})")
    lines.append(f"총 거리: {route.total_distance:.0f}m, 예상 시간: {route.total_time:.0f}초")
    lines.append(f"DP 수: {len(route.decision_points)}개")
    lines.append("")

    current_found = False
    for dp in route.decision_points:
        marker = ""
        if current_dp_id and dp.dp_id == current_dp_id:
            marker = " [현재 위치]"
            current_found = True

        line = f"- {dp.dp_id} ({dp.dp_type}){marker}: {dp.guidance.primary}"
        if dp.selected_landmark:
            lm = dp.selected_landmark
            line += f" | 랜드마크: {lm.name} ({lm.position}, {lm.distance:.0f}m)"
        lines.append(line)

    if current_dp_id and not current_found:
        lines.append(f"\n현재 DP ID: {current_dp_id} (목록에서 찾을 수 없음)")

    return "\n".join(lines)


_SYSTEM_PROMPT_TEMPLATE = """\
당신은 시각장애인 보행자를 위한 친절한 길안내 도우미입니다.
사용자가 현재 걷고 있는 경로에 대해 질문하면, 아래 경로 정보를 바탕으로 한국어로 친절하고 간결하게 답변하세요.

규칙:
- 경로 정보에 있는 내용만 답변하세요. 추측하지 마세요.
- 랜드마크 이름, 방향(왼쪽/오른쪽), 거리 등 구체적 정보를 포함하세요.
- 답변은 2~3문장으로 짧고 명확하게 하세요.
- 사용자가 불안해하지 않도록 따뜻한 톤을 유지하세요.

경로 정보:
{route_context}"""


async def chat(
    request: ConversationRequest,
    route: RouteResponse,
) -> ConversationResponse:
    """Answer a user question using route context via OpenAI Chat API.

    Args:
        request: User's question with route_id and optional current_dp_id.
        route: Cached RouteResponse for context.

    Returns:
        ConversationResponse with the assistant's answer.
    """
    route_context = _build_route_context(route, request.current_dp_id)
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
