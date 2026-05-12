"""대화형 모드 답변 LLM 수동 확인용 REPL.

사용법:
    cd services/dp-pipeline
    python3 main_llm.py

명령:
    /show              현재 상태(current_dp, completed) + 컨텍스트 출력
    /set current dp-X  current_dp_id 변경
    /set completed dp-0,dp-1   완료 DP 집합 교체
    /reset             초기 상태로 복귀
    /exit, /quit       종료
    (그 외 입력은 모두 LLM에 질문으로 전송)

OPENAI_API_KEY는 .env(repo root 또는 services/dp-pipeline)에서 자동 로드됩니다.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE / "tests"))
from test_conversation_service import _make_route  # noqa: E402

from conversation_service import _build_route_context, chat  # noqa: E402
from schemas import ConversationRequest  # noqa: E402


INITIAL_CURRENT = "dp-1"
INITIAL_COMPLETED = {"dp-0"}


class Session:
    def __init__(self) -> None:
        self.route = _make_route()
        self.current_dp_id: str | None = INITIAL_CURRENT
        self.completed: set[str] = set(INITIAL_COMPLETED)

    def show(self) -> None:
        print(f"\n[STATE] current_dp_id={self.current_dp_id!r}  completed={sorted(self.completed)}")
        print("─" * 60)
        print(_build_route_context(self.route, self.current_dp_id, self.completed))
        print("─" * 60)

    def reset(self) -> None:
        self.current_dp_id = INITIAL_CURRENT
        self.completed = set(INITIAL_COMPLETED)
        print(f"[reset] current={self.current_dp_id}, completed={sorted(self.completed)}")

    def set_current(self, value: str) -> None:
        self.current_dp_id = value if value else None
        print(f"[set] current_dp_id = {self.current_dp_id!r}")

    def set_completed(self, value: str) -> None:
        self.completed = {s.strip() for s in value.split(",") if s.strip()}
        print(f"[set] completed = {sorted(self.completed)}")

    async def ask(self, question: str) -> None:
        req = ConversationRequest(
            question=question,
            route_id=self.route.route_id,
            current_dp_id=self.current_dp_id,
        )
        resp = await chat(req, self.route, completed_dp_ids=self.completed)
        print(f"A> {resp.answer}\n")


def handle_command(s: Session, line: str) -> bool:
    """명령 처리. True면 REPL 계속, False면 종료."""
    parts = line.strip().split(maxsplit=2)
    cmd = parts[0]

    if cmd in ("/exit", "/quit"):
        return False
    if cmd == "/show":
        s.show()
        return True
    if cmd == "/reset":
        s.reset()
        return True
    if cmd == "/set" and len(parts) >= 3:
        field, value = parts[1], parts[2]
        if field == "current":
            s.set_current(value)
        elif field == "completed":
            s.set_completed(value)
        else:
            print(f"[?] 알 수 없는 필드: {field} (current | completed)")
        return True
    print(f"[?] 알 수 없는 명령: {line}")
    return True


async def main() -> None:
    s = Session()
    print("대화형 답변 LLM REPL")
    print("도움말: /show, /set current dp-X, /set completed dp-0,dp-1, /reset, /exit")
    s.show()

    while True:
        try:
            line = input("Q> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line.startswith("/"):
            if not handle_command(s, line):
                break
            continue
        try:
            await s.ask(line)
        except Exception as exc:
            print(f"[error] {exc}\n")


if __name__ == "__main__":
    asyncio.run(main())
