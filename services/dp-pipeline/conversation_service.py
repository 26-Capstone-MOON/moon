"""Conversation Service — Mode B 대화형 답변 LLM.

사용자 질문에 대해 캐시된 경로 컨텍스트를 바탕으로 한국어 응답을 생성한다.
의도(intent) 분류는 별도로 두지 않고 시스템 프롬프트의 유형 가이드만으로 분기한다.
사양: services/dp-pipeline/.claude/rules/conversation.md
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from config import settings
from schemas import (
    ConversationRequest,
    ConversationResponse,
    DecisionPoint,
    RouteResponse,
)

logger = logging.getLogger(__name__)

_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_MODEL = "gpt-4o"
_TIMEOUT_S = 15.0
_TEMPERATURE = 0.25
_MAX_TOKENS = 300

_FALLBACK_ANSWER = "죄송해요, 지금 답변을 드리기 어렵습니다. 잠시 후 다시 시도해 주세요."

_POSITION_KO = {"LEFT": "왼쪽", "RIGHT": "오른쪽", "FRONT": "전방"}

# 사용자가 랜드마크 외관/모습을 묻는 질문일 때 파노라마 표시 트리거
_PANORAMA_KEYWORDS = (
    "어떻게 생겼",
    "외관",
    "모양",
    "모습",
    "보여줘",
    "보여 줘",
    "어떤 건물",
    "어떻게 보여",
    "이 건물",
    "저 건물",
)

# 사용자가 현재 경로 진행 여부를 확인하는 질문일 때 deterministic 응답 트리거
_POSITION_CONFIRM_KEYWORDS = (
    "잘 가고 있",
    "잘 가고 계",
    "맞게 가고 있",
    "이 길 맞",
    "제대로 가고 있",
    "거 맞아",
)


def _should_show_panorama(question: str) -> bool:
    """질문에 외관·모습 관련 키워드가 포함되어 있으면 파노라마 표시."""
    return any(kw in question for kw in _PANORAMA_KEYWORDS)


def _should_confirm_position(question: str) -> bool:
    """질문에 위치확인 키워드가 포함되어 있으면 정형 답변 분기."""
    return any(kw in question for kw in _POSITION_CONFIRM_KEYWORDS)


def _find_appearance(
    route: RouteResponse,
    current_dp_id: Optional[str],
) -> Optional[str]:
    """현재 DP의 appearance를 찾고, 없으면 이후 DP에서 첫 appearance를 찾는다."""
    dps = route.decision_points
    start_idx = 0
    if current_dp_id:
        for i, dp in enumerate(dps):
            if dp.dp_id == current_dp_id:
                start_idx = i
                break
    for dp in dps[start_idx:]:
        if dp.selected_landmark and dp.selected_landmark.appearance:
            return dp.selected_landmark.appearance
    return None


def _find_position_confirm(
    route: RouteResponse,
    current_dp_id: Optional[str],
) -> Optional[str]:
    """현재 DP의 position_confirm 문구를 찾고, 없으면 이후 DP에서 첫 값을 찾는다."""
    dps = route.decision_points
    start_idx = 0
    if current_dp_id:
        for i, dp in enumerate(dps):
            if dp.dp_id == current_dp_id:
                start_idx = i
                break
    for dp in dps[start_idx:]:
        if dp.selected_landmark and dp.selected_landmark.position_confirm:
            return dp.selected_landmark.position_confirm
    return None


# ---------------------------------------------------------------------------
# Progress label
# ---------------------------------------------------------------------------

def _progress_label(done: int, total: int) -> str:
    """진행률을 한국어 라벨로 변환."""
    if total <= 0 or done <= 0:
        return "출발 직후"
    ratio = done / total
    if ratio >= 1.0:
        return "다 왔어요"
    if ratio >= 0.7:
        return "꽤 왔어요"
    if ratio >= 0.3:
        return "중간쯤"
    return "출발 직후"


# ---------------------------------------------------------------------------
# Remaining-time estimate
# ---------------------------------------------------------------------------

def _estimate_remaining_seconds(
    route: RouteResponse,
    current_dp_id: Optional[str],
    completed_dp_ids: Optional[set[str]],
) -> Optional[float]:
    """현재 진행도 기준 남은 시간(초) 추정.

    우선순위: current_dp의 distance_from_start → completed 중 최댓값 → 0
    total_distance/total_time이 없거나 0이면 None.
    """
    total_dist = route.total_distance or 0.0
    total_time = route.total_time or 0.0
    if total_dist <= 0 or total_time <= 0:
        return None

    covered = 0.0
    if current_dp_id:
        for dp in route.decision_points:
            if dp.dp_id == current_dp_id:
                covered = dp.distance_from_start
                break
    if covered == 0.0 and completed_dp_ids:
        for dp in route.decision_points:
            if dp.dp_id in completed_dp_ids:
                covered = max(covered, dp.distance_from_start)

    remaining_dist = max(0.0, total_dist - covered)
    return total_time * (remaining_dist / total_dist)


def _format_remaining_time(seconds: Optional[float]) -> Optional[str]:
    """잔여 시간을 한국어로 표현 (절대 거리·초 단위 숫자는 노출하지 않음)."""
    if seconds is None:
        return None
    if seconds < 30:
        return "곧 도착"
    minutes = int((seconds + 30) // 60)
    if minutes <= 1:
        return "약 1분"
    return f"약 {minutes}분"


# ---------------------------------------------------------------------------
# DP rendering helpers
# ---------------------------------------------------------------------------

def _render_landmark(dp: DecisionPoint) -> Optional[str]:
    lm = dp.selected_landmark
    if lm is None:
        return None
    pos_ko = _POSITION_KO.get(lm.position, lm.position)
    return f"{pos_ko}에 {lm.name} ({lm.match_status})"


def _render_dp_block(dp: DecisionPoint) -> str:
    lines = [f"- 유형: {dp.dp_type}"]
    if dp.guidance and dp.guidance.primary:
        lines.append(f"- 안내: \"{dp.guidance.primary}\"")
    if dp.guidance and dp.guidance.pre_alert:
        lines.append(f"- 미리알림: \"{dp.guidance.pre_alert}\"")
    lm_line = _render_landmark(dp)
    if lm_line:
        lines.append(f"- 랜드마크: {lm_line}")
    if dp.selected_landmark and dp.selected_landmark.appearance:
        lines.append(f"- 외관: {dp.selected_landmark.appearance}")
    return "\n".join(lines)


def _render_dp_summary(dp: DecisionPoint) -> str:
    """완료 목록/다음 구간용 한 줄 요약."""
    head = f"{dp.dp_id} ({dp.dp_type})"
    if dp.guidance and dp.guidance.primary:
        return f"{head} — {dp.guidance.primary}"
    return head


# ---------------------------------------------------------------------------
# Route context builder
# ---------------------------------------------------------------------------

def _build_route_context(
    route: RouteResponse,
    current_dp_id: Optional[str],
    completed_dp_ids: Optional[set[str]] = None,
) -> str:
    """경로 컨텍스트를 4개 섹션 문자열로 생성.

    규칙:
    - 거리 숫자(예: "14m") 금지
    - 위치는 한국어로 (LEFT→왼쪽, RIGHT→오른쪽, FRONT→전방)
    - current_dp 없거나 매칭 실패 시 [현재 구간] 생략
    - completed_dp_ids None이면 [진행 상황] 생략
    """
    dps = route.decision_points
    total = len(dps)

    current_idx: Optional[int] = None
    if current_dp_id:
        for i, dp in enumerate(dps):
            if dp.dp_id == current_dp_id:
                current_idx = i
                break

    sections: list[str] = []

    # [경로 요약]
    summary: list[str] = ["[경로 요약]"]
    summary.append(f"목적지: {route.dest_name or '목적지'}")
    summary.append(f"총 DP: {total}개")
    sections.append("\n".join(summary))

    # [진행 상황]
    # completed_dp_ids가 있으면 그것 기반, 없으면 current_idx 기반으로 라벨링
    if completed_dp_ids is not None:
        done_count = sum(1 for dp in dps if dp.dp_id in completed_dp_ids)
    elif current_idx is not None:
        done_count = current_idx
    else:
        done_count = 0
    progress_lines = ["[진행 상황]"]
    progress_lines.append(
        f"완료한 DP: {done_count}/{total} ({_progress_label(done_count, total)})"
    )
    remaining_label = _format_remaining_time(
        _estimate_remaining_seconds(route, current_dp_id, completed_dp_ids)
    )
    if remaining_label is not None:
        progress_lines.append(f"남은 시간: {remaining_label}")
    if completed_dp_ids:
        completed_dps = [dp for dp in dps if dp.dp_id in completed_dp_ids]
        if completed_dps:
            progress_lines.append("완료 목록 (위→아래 = 오래된→최근):")
            last_idx = len(completed_dps) - 1
            for i, dp in enumerate(completed_dps):
                marker = "  ← 방금 지나온 곳" if i == last_idx else ""
                progress_lines.append(f"- {_render_dp_summary(dp)}{marker}")
    sections.append("\n".join(progress_lines))

    # [현재 구간]
    if current_idx is not None:
        current_lines = ["[현재 구간]", _render_dp_block(dps[current_idx])]
        sections.append("\n".join(current_lines))

    # [다음 구간]
    next_start = (current_idx + 1) if current_idx is not None else 0
    next_dps = dps[next_start : next_start + 2]
    if next_dps:
        next_lines = ["[다음 구간]"]
        for dp in next_dps:
            next_lines.append(f"- {_render_dp_summary(dp)}")
            if dp.selected_landmark and dp.selected_landmark.appearance:
                next_lines.append(f"  외관: {dp.selected_landmark.appearance}")
        sections.append("\n".join(next_lines))

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = """\
당신은 길안내 도우미 서비스 MOON 입니다.
사용자가 이어폰으로 묻는 질문에 대해 아래 [경로 정보]만을 근거로 답합니다.

[톤 규칙]
- 친근체 종결을 사용하세요: "~거예요", "~하세요", "~나와요"
- 2~3문장으로 짧고 명확하게 답하세요
- 절대 거리를 숫자로 말하지 마세요 (예: "30m 앞"은 금지). 대신 "곧", "조금만 더 가면"을 쓰세요
- 확인 질문은 쓰지 마세요 (예: "보이시죠?" 금지)
- 안내 시작 멘트는 쓰지 마세요 (예: "안내를 시작합니다" 금지)
- 랜드마크가 있으면 답변에서 그 이름을 직접 부르세요. "거기서", "그쪽으로", "그곳에서" 같은 모호한 지시어는 금지입니다 (예: "거기서 우회전" → "올리브영을 끼고 우회전")
- 동작 종결은 "~하면 돼요" 또는 "~하면 됩니다"를 쓰세요. "~하는 게 맞아요", "~해야 해요" 같은 평가·단정형은 어색하니 금지입니다 (예: "우회전하는 게 맞아요" → "우회전하면 됩니다")
- 답변의 핵심을 다 말했으면 거기서 끝내세요. "그대로 진행하세요", "계속 가세요" 같은 군더더기 멘트를 답변 끝에 덧붙이지 마세요 (위치 확인 유형에서만 명시적으로 필요)
- 사용자는 이미 길 안내를 받는 중입니다. 목적지·출발지·경로를 사용자에게 되묻지 마세요. "어디로 가세요?", "어디서 출발하셨어요?", "도와드릴까요?" 같은 질문은 금지입니다 (목적지는 [경로 정보]에 이미 있음)

[질문 유형별 응답 방향]
- 인사·잡담 ("안녕", "수고했어", "고마워"): 짧게 받아준 뒤 [현재 구간] 안내를 자연어로 한 번 더 알려주세요. 목적지를 되묻지 말고, 이미 안내 중이라는 전제로 응답합니다 (예: "안녕하세요! 곧 오른쪽에 올리브영이 보일 거예요.")
- 위치 확인 ("지금 어디쯤이야?", "지금 어딘데?"): [현재 구간]의 랜드마크와 방향을 활용해 "곧 ~이 보일 거예요. 그때까지 그대로 가세요" 형태로 답하세요. 다음 동작(우회전·좌회전·횡단보도 건너기·계단 등)은 명령하지 마세요. "직진하세요"처럼 특정 동작을 단정하지 말고, "그대로 가세요", "그대로 진행하세요", "계속 가세요"처럼 **행위 중립 표현**을 사용합니다. 사용자가 지금 무슨 행위(직진·횡단·계단·우측보행)를 하고 있는지 컨텍스트만으로는 단정할 수 없기 때문입니다
- 다음 동작 ("다음에 뭐 해?"): [현재 구간]의 안내 또는 미리알림을 자연어로 풀어주세요. 동작 대상은 랜드마크 이름으로 다시 명시하세요
- 진행도 ("얼마나 남았어?", "거의 다 왔어?"): [진행 상황]의 "남은 시간" 값을 그대로 사용해 "약 N분 정도 남았어요" 형태로 답하세요. "곧 도착"이면 "거의 다 왔어요"로 표현합니다. DP 개수, N/M 카운트, 진행률 라벨은 답변에 포함하지 마세요
- 지나온 길 / 회고 ("아까 어디 지났지?", "방금 어디 다녀왔어?"): [진행 상황] 완료 목록에서 `← 방금 지나온 곳` 마커가 붙은 항목을 찾아, 그 DP의 안내와 랜드마크를 자연어로 설명하세요. DEPARTURE라도 마커가 붙어 있으면 그 안내 내용을 활용해 답하세요. 완료 목록 자체가 아예 비어 있을 때만 "아직 출발 지점이에요"라고 답하세요
- 주변 정보 ("근처에 뭐 있어?"): [현재 구간]의 랜드마크만 사용하세요. 없는 정보 추측 금지
- 외관·모습 ("어떻게 생겼어?", "외관", "모양", "보여줘", "어떤 건물이야?"): [현재 구간] 또는 [다음 구간]의 "외관" 정보를 자연스러운 한국어로 풀어서 답하세요.
  · 외관 정보를 그대로 복사하지 말고 자연스러운 문장으로 변형하세요
  · 매번 표현을 다르게 (어휘 다양성)
  · 1~2문장으로 짧게
  · 추측하거나 상상으로 묘사하지 말 것 — 컨텍스트에 있는 외관 정보만 사용
  · 외관 정보가 없으면 "잘 보이지 않아요" 정도로 답하세요
- 경로 이탈 우려 ("길 잘못 든 것 같아"): "지금 위치 기준으로는 ..." 형태로 [현재 구간] 안내를 자연어로 재확인하세요

[금지사항]
- [경로 정보]에 없는 사실을 추측하지 마세요
- 새 경로를 안내하거나 재경로를 약속하지 마세요 (해당 권한 없음)
- 빈 답변이나 "잘 모르겠어요"만으로 끝내지 마세요

[경로 정보]
{route_context}"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def chat(
    request: ConversationRequest,
    route: RouteResponse,
    completed_dp_ids: Optional[set[str]] = None,
) -> ConversationResponse:
    """Mode B 대화형 답변 생성.

    경로 컨텍스트를 시스템 프롬프트에 주입해 단일 OpenAI 호출로 응답한다.
    분류기를 두지 않고 프롬프트의 유형 가이드만으로 분기한다.
    """
    show_panorama = _should_show_panorama(request.question)

    # 외관 질문은 LLM을 거치지 않고 mock의 appearance 문자열을 그대로 반환한다.
    # LLM이 paraphrasing해서 mock 원문이 변형되는 것을 방지.
    if show_panorama:
        appearance = _find_appearance(route, request.current_dp_id)
        if appearance:
            return ConversationResponse(
                answer=appearance,
                show_panorama=True,
                target_dp_id=request.current_dp_id,
            )

    # 위치확인 질문도 LLM을 거치지 않고 mock의 position_confirm 문자열을 그대로 반환한다.
    # 외관과 동일한 패턴 — 시연 안정성을 위해 정형 답변 보장.
    if _should_confirm_position(request.question):
        confirm = _find_position_confirm(route, request.current_dp_id)
        if confirm:
            return ConversationResponse(
                answer=confirm,
                show_panorama=False,
                target_dp_id=None,
            )

    route_context = _build_route_context(route, request.current_dp_id, completed_dp_ids)
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(route_context=route_context)

    payload = {
        "model": _MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.question},
        ],
        "temperature": _TEMPERATURE,
        "max_tokens": _MAX_TOKENS,
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
        answer = _FALLBACK_ANSWER

    target_dp_id = request.current_dp_id if show_panorama else None

    return ConversationResponse(
        answer=answer,
        show_panorama=show_panorama,
        target_dp_id=target_dp_id,
    )
