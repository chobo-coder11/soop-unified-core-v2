from __future__ import annotations

import inspect

import app_v7
import overlay_server_v5 as base_overlay
from overlay_server_v7 import OverlayServerV7
from quiz_engine_v7 import QuizEngineV7, UI_VERSION


def main() -> None:
    engine = QuizEngineV7()
    state = engine.public_state()
    assert state["app"]["version"] == UI_VERSION == "0.7.0"

    # The overlay must carry the large-type and motion system while keeping the
    # stable v5 SSE/networking implementation underneath.
    assert "v0.7 broadcast readability" in base_overlay.QUIZ
    assert "v7-choice" in base_overlay.QUIZ
    assert "clamp(42px,4.2vw,78px)" in base_overlay.QUIZ
    assert "v7-rank-in" in base_overlay.RANK

    # Controller safety/readability invariants.
    source = inspect.getsource(app_v7.QuizAppV7)
    assert "LIVE MODE" in source
    assert "font=(FONT, 36" in source
    assert "height=88" in source
    assert "F9" in source
    assert "문제 편집과 설정을 잠급니다" in source

    server = OverlayServerV7(engine, preferred_port=8871)
    try:
        assert "/overlay/quiz" in server.quiz_url
        assert "/overlay/rank" in server.rank_url
    finally:
        server.server.server_close()
    print("v0.7 broadcast UX regression: PASS")


if __name__ == "__main__":
    main()
