from __future__ import annotations

import sys
import time

from common import Question
from overlay_server_v10 import OverlayServerV10
from quiz_engine_v10 import QuizEngineV10


def build_engine(target: str) -> QuizEngineV10:
    q = Question(
        kind="multiple",
        prompt="긴 문제와 여섯 개 보기가 동시에 표시되는 실제 방송 상황을 가정한 레이어 검증 문제입니다. 화면 높이가 720픽셀이어도 문제, 보기, 진행 상태가 잘리지 않아야 합니다.",
        choices=[
            "첫 번째 보기 · 긴 문장도 자연스럽게 줄바꿈되어야 합니다.",
            "두 번째 보기 · 정답이며 공개 후 초록색으로 명확하게 강조되어야 합니다.",
            "세 번째 보기 · 방송용 브라우저 소스의 폭이 좁아져도 읽을 수 있어야 합니다.",
            "네 번째 보기 · 문제 공개 단계에서는 정답을 절대 미리 표시하면 안 됩니다.",
            "다섯 번째 보기 · 답변 마감 후에도 문제와 보기가 화면에 그대로 남아야 합니다.",
            "여섯 번째 보기 · 정답 공개에서도 전체 카드가 화면 밖으로 잘리면 안 됩니다.",
        ],
        answer="2",
        accepted_answers=["private-alias"],
        duration_sec=120,
        auto_close_time=False,
        score_multiplier=2.0,
    )
    engine = QuizEngineV10()
    engine.set_questions([q])
    engine.enter_practice()
    engine.start_recruitment()
    engine.simulate_join(36)
    engine.close_recruitment()
    engine.show_question()
    if target in {"ANSWERING", "QUESTION_CLOSED", "ANSWER_REVEALED"}:
        engine.open_answers(0)
        engine.simulate_answers()
    if target in {"QUESTION_CLOSED", "ANSWER_REVEALED"}:
        engine.close_answers()
    if target == "ANSWER_REVEALED":
        engine.reveal_answer()
    if engine.state != target:
        raise SystemExit(f"fixture state mismatch: expected {target}, got {engine.state}")
    return engine


def main() -> None:
    target = (sys.argv[1] if len(sys.argv) > 1 else "QUESTION_SHOWN").upper()
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8898
    engine = build_engine(target)
    server = OverlayServerV10(engine, preferred_port=port)
    server.start()
    print(server.quiz_url, flush=True)
    try:
        time.sleep(90)
    finally:
        server.stop()


if __name__ == "__main__":
    main()
