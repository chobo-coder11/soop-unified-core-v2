from __future__ import annotations

import http.client
import inspect
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request

import app_v9
from common import Question
from overlay_server_v9 import HandlerV9, OverlayServerV9, QUIZ
from quiz_engine_v9 import QuizEngineV9, UI_VERSION


def sample_questions() -> list[Question]:
    return [
        Question(
            kind="multiple",
            prompt="방송용 메인 퀴즈 레이어가 긴 문제 문장과 여섯 개의 보기를 동시에 표시하더라도 문제와 보기가 잘리지 않아야 합니다. 다음 중 정답은 무엇인가요?",
            choices=[
                "첫 번째 보기입니다. 문장이 조금 길어져도 레이어 안에서 자연스럽게 줄바꿈되어야 합니다.",
                "두 번째 보기 서울입니다. 이것이 테스트 정답입니다.",
                "세 번째 보기 역시 긴 문장을 사용해 실제 방송 환경의 레이아웃을 검증합니다.",
                "네 번째 보기입니다. 1280×720에서도 화면 밖으로 밀려나면 안 됩니다.",
                "다섯 번째 보기입니다. 최대 여섯 개 보기까지 안정적으로 배치해야 합니다.",
                "여섯 번째 보기입니다. 정답 공개 시에도 전체 레이아웃이 유지되어야 합니다.",
            ],
            answer="2",
            accepted_answers=["절대 브라우저로 미리 노출되면 안 되는 별칭"],
            duration_sec=120,
            auto_close_time=False,
            score_multiplier=2.0,
            note="진행자 전용 메모",
        ),
        Question(kind="ox", prompt="두 번째 문제입니다.", answer="O", duration_sec=30, auto_close_time=False),
    ]


def assert_question_private(state: dict) -> None:
    assert state["question"] is None
    dumped = json.dumps(state, ensure_ascii=False)
    assert "절대 브라우저로 미리 노출되면 안 되는 별칭" not in dumped
    assert "진행자 전용 메모" not in dumped


def read_sse_state(response: http.client.HTTPResponse, target: str | None = None, max_events: int = 8) -> dict:
    seen = 0
    while seen < max_events:
        raw = response.readline()
        if not raw:
            raise AssertionError("SSE stream ended unexpectedly")
        line = raw.decode("utf-8", "replace").strip()
        if not line.startswith("data: "):
            continue
        state = json.loads(line[6:])
        seen += 1
        if target is None or state.get("state") == target:
            return state
    raise AssertionError(f"SSE did not deliver target state: {target}")


def main() -> None:
    assert UI_VERSION == "0.9.0"

    # ----- state machine + answer privacy -----
    engine = QuizEngineV9()
    engine.set_questions(sample_questions())
    engine.enter_practice()
    ready = engine.public_state()
    assert ready["app"]["version"] == "0.9.0"
    assert_question_private(ready)

    assert engine.start_recruitment()
    assert_question_private(engine.public_state())
    assert engine.simulate_join(24) == 24
    assert engine.close_recruitment()
    assert engine.state == "LOCKED"
    assert_question_private(engine.public_state())

    assert engine.show_question()
    shown = engine.public_state()
    assert shown["state"] == "QUESTION_SHOWN"
    assert shown["question"]["prompt"].startswith("방송용 메인 퀴즈")
    assert len(shown["question"]["choices"]) == 6
    assert "answer" not in shown["question"]
    assert "accepted_answers" not in shown["question"]
    assert "rank_points" not in shown["question"]
    assert shown["correct"] == 0 and shown["firstCorrect"] == []

    # A second show call must not clear/re-show the current round.
    assert not engine.show_question()
    assert engine.state == "QUESTION_SHOWN"

    assert engine.open_answers(0)
    assert engine.simulate_answers() > 0
    answering = engine.public_state()
    assert answering["state"] == "ANSWERING"
    assert "answer" not in answering["question"]
    assert answering["correct"] == 0
    assert answering["firstCorrect"] == []
    assert answering["answerDistribution"] == []

    assert engine.close_answers()
    closed = engine.public_state()
    assert closed["state"] == "QUESTION_CLOSED"
    assert "answer" not in closed["question"]
    assert closed["correct"] == 0

    assert engine.reveal_answer()
    revealed = engine.public_state()
    assert revealed["state"] == "ANSWER_REVEALED"
    assert revealed["question"]["answer"] == "2"
    assert revealed["question"]["score_multiplier"] == 2.0
    assert revealed["correct"] > 0
    assert revealed["firstCorrect"]
    assert revealed["answerDistribution"]
    dumped = json.dumps(revealed, ensure_ascii=False)
    assert "절대 브라우저로 미리 노출되면 안 되는 별칭" not in dumped
    assert "진행자 전용 메모" not in dumped

    # show_question cannot bypass next_question after reveal.
    assert not engine.show_question()
    assert engine.state == "ANSWER_REVEALED"
    assert engine.next_question()
    assert engine.state == "LOCKED" and engine.current_index == 1
    assert_question_private(engine.public_state())

    # Invalid question configuration must fail loudly instead of showing a broken layer.
    bad = QuizEngineV9()
    bad.set_questions([Question(kind="multiple", prompt="잘못된 객관식", choices=["A", "B"], answer="9")])
    bad.enter_practice(); assert bad.start_recruitment(); assert bad.close_recruitment()
    assert not bad.show_question()
    assert "1~2번" in bad.last_transition_error

    # Problem-void flow used to leave the main controller with a dead action button.
    voided = QuizEngineV9()
    voided.set_questions([Question(kind="ox", prompt="무효 처리 테스트", answer="O", auto_close_time=False)])
    voided.enter_practice(); assert voided.start_recruitment(); assert voided.close_recruitment(); assert voided.show_question(); assert voided.open_answers(0); assert voided.close_answers()
    assert voided.void_current_question()
    assert voided.state == "QUESTION_VOID"
    assert voided.next_question()
    assert voided.state == "FINISHED"

    # ----- browser layer source regressions -----
    assert "fitLayout" in QUIZ
    assert "data-overflow" not in QUIZ  # set through dataset at runtime, not hard-coded stale markup
    assert "document.body.dataset.overflow" in QUIZ
    assert "QUESTION_SHOWN" in QUIZ and "ANSWER_REVEALED" in QUIZ
    assert "answer-banner" in QUIZ
    assert "START 대기" in QUIZ
    assert "레이어 연결 재시도 중" in QUIZ
    assert "fit-4" in QUIZ

    node = shutil.which("node")
    if node:
        scripts = re.findall(r"<script>(.*?)</script>", QUIZ, re.S)
        assert len(scripts) == 1
        fd, path = tempfile.mkstemp(suffix=".js")
        os.close(fd)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(scripts[0])
            subprocess.run([node, "--check", path], check=True, capture_output=True, text=True)
        finally:
            try: os.unlink(path)
            except OSError: pass

    sse_source = inspect.getsource(HandlerV9._events)
    assert "snapshot_version" in sse_source
    assert "last = snapshot_version" in sse_source
    assert "last = self.engine.state_version" not in sse_source

    app_source = inspect.getsource(app_v9.QuizAppV9.primary_action)
    assert "0.42" in app_source
    assert '"QUESTION_VOID"' in app_source
    assert "current_question_error" in app_source

    # ----- actual HTTP/SSE integration -----
    live = QuizEngineV9()
    live.set_questions(sample_questions())
    live.enter_practice()
    server = OverlayServerV9(live, preferred_port=8890)
    server.start()
    try:
        time.sleep(0.08)
        health = json.loads(urllib.request.urlopen(server.health_url, timeout=3).read().decode())
        assert health == {"ok": True, "version": "0.9.0", "transport": "sse-v2"}
        html = urllib.request.urlopen(server.quiz_url, timeout=3).read().decode("utf-8")
        assert "fitLayout" in html and "snapshot_version" not in html

        conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=4)
        conn.request("GET", "/api/events")
        response = conn.getresponse()
        assert response.status == 200
        initial = read_sse_state(response)
        assert initial["state"] == "READY"

        assert live.start_recruitment()
        recruitment = read_sse_state(response, "RECRUITING")
        assert recruitment["question"] is None

        # Move through two states faster than the SSE coalescing interval. The
        # stream may coalesce LOCKED, but it must never lose the final reveal state.
        assert live.close_recruitment()
        assert live.show_question()
        shown_event = read_sse_state(response, "QUESTION_SHOWN", max_events=6)
        assert shown_event["question"]["prompt"].startswith("방송용 메인 퀴즈")
        assert "answer" not in shown_event["question"]

        assert live.open_answers(0)
        answering_event = read_sse_state(response, "ANSWERING", max_events=6)
        assert answering_event["deadlineEpochMs"] is not None
        conn.close()
    finally:
        server.stop()

    print("v0.9 question reveal / overlay / SSE regression: PASS")


if __name__ == "__main__":
    main()
