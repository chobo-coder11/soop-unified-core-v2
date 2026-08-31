from __future__ import annotations

import overlay_server_v5 as base_overlay
from overlay_server_v6 import OverlayServerV6
from quiz_engine_v6 import QuizEngineV6, UI_VERSION


def main() -> None:
    engine = QuizEngineV6()
    state = engine.public_state()
    assert state["app"]["version"] == UI_VERSION == "0.6.0"
    # Importing v6 injects the polished CSS into the stable v5 routes.
    assert "v0.6 visual system" in base_overlay.QUIZ
    assert "style-game" in base_overlay.QUIZ
    assert "row:nth-child(1)" in base_overlay.RANK
    server = OverlayServerV6(engine, preferred_port=8870)
    try:
        assert "/overlay/quiz" in server.quiz_url
        assert "/overlay/rank" in server.rank_url
    finally:
        server.server.server_close()
    print("v0.6 design wrapper regression: PASS")


if __name__ == "__main__":
    main()
