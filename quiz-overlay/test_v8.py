from __future__ import annotations

import inspect

import app_v8
from overlay_server_v8 import OverlayServerV8
from quiz_engine_v8 import QuizEngineV8, UI_VERSION


def main() -> None:
    engine = QuizEngineV8()
    state = engine.public_state()
    assert state["app"]["version"] == UI_VERSION == "0.8.0"

    source = inspect.getsource(app_v8.QuizAppV8)
    run_source = inspect.getsource(app_v8.QuizAppV8._build_run_page)

    # v0.8 intentionally removes the clutter visible in the v0.7 real-world screenshot.
    assert "width=190" in source
    assert "height=64" in run_source
    assert "실시간 순위" in run_source
    assert "최근 답변" in run_source
    assert "운영 · 내보내기" in run_source
    assert "테스트 참가자 +12" in run_source
    assert "self.practice_tools.grid_remove()" in run_source
    assert "CTkTabview" not in run_source
    assert "CTkSwitch" not in source
    assert "SAFE" not in source
    assert "set_widget_scaling(1.0)" in source
    assert "wraplength=max(360" in source

    server = OverlayServerV8(engine, preferred_port=8872)
    try:
        assert "/overlay/quiz" in server.quiz_url
        assert "/overlay/top10" in server.rank_url
    finally:
        server.server.server_close()

    print("v0.8 controller UX regression: PASS")


if __name__ == "__main__":
    main()
