from __future__ import annotations

import json
import urllib.request

from app_v10 import (
    POLICY_TO_UI,
    SCORE_TO_UI,
    QuizAppV10,
)
from common import Question
from overlay_server_v10 import OverlayServerV10
from quiz_engine_v10 import QuizEngineV10, UI_VERSION


def main() -> None:
    assert UI_VERSION == "0.10.0"
    engine = QuizEngineV10()
    engine.set_questions([Question(prompt="2 + 2는?", choices=["3", "4", "5"], answer="2")])
    state = engine.public_state()
    assert state["app"]["version"] == "0.10.0"

    assert "scoring" not in " ".join(SCORE_TO_UI.values()).lower()
    assert SCORE_TO_UI["all"] == "맞힌 사람 모두 점수"
    assert POLICY_TO_UI["last"] == "마지막에 보낸 답으로 채점"

    assert QuizAppV10._validate_editor_question(Question(prompt="", choices=["1", "2"], answer="1"))
    assert QuizAppV10._validate_editor_question(Question(kind="multiple", prompt="문제", choices=["하나"], answer="1"))
    assert QuizAppV10._validate_editor_question(Question(kind="short", prompt="문제", answer=""))
    assert QuizAppV10._validate_editor_question(Question(kind="number", prompt="문제", answer="abc"))
    assert QuizAppV10._validate_editor_question(Question(kind="ox", prompt="문제", answer="O")) == ""

    server = OverlayServerV10(engine, preferred_port=8920)
    server.start()
    try:
        health = json.loads(urllib.request.urlopen(server.health_url, timeout=3).read().decode("utf-8"))
        assert health["version"] == "0.10.0"
        page = urllib.request.urlopen(server.quiz_url, timeout=3).read().decode("utf-8")
        assert "const INITIAL=" in page
        assert "topBar" in page
        assert "function top(s)" not in page
    finally:
        server.stop()

    print("v0.10 engine/editor/overlay regression passed")


if __name__ == "__main__":
    main()
