from __future__ import annotations

import threading
import time

from common import Question, utc_now
from quiz_engine_v3 import QuizEngineV3


def chat(seq: int, uid: str, nick: str, message: str) -> dict:
    return {"user": {"id": uid, "nickname": nick}, "message": message, "receivedAt": utc_now().isoformat()}


def test_state_and_order() -> None:
    e = QuizEngineV3()
    e.set_questions([Question(kind="multiple", prompt="정답?", choices=["A", "B", "C"], answer="2", duration_sec=30)])
    e.set_connected("streamer")
    assert e.start_recruitment()
    for i in range(1, 101):
        e.process_chat(i, f"u{i}", ) if False else None
        e.process_chat(i, chat(i, f"u{i}", f"닉{i}", "!참여"))
    assert len(e.participants) == 100
    assert e.close_recruitment()
    assert e.show_question()
    assert e.open_answers(100)
    e.process_chat(102, chat(102, "u2", "닉2", "!2"))
    e.process_chat(101, chat(101, "u1", "닉1", "!2"))
    e.process_chat(103, chat(103, "u3", "닉3", "!1"))
    assert e.correct_order == ["u1", "u2"]
    assert e.close_answers()
    assert e.reveal_answer()
    assert e.participants["u1"].correct_count == 1
    assert e.participants["u3"].correct_count == 0


def test_retry_before_reveal() -> None:
    e = QuizEngineV3()
    e.set_questions([Question(prompt="x", choices=["a", "b"], answer="1")])
    e.enter_practice()
    e.start_recruitment(); e.simulate_join(12); e.close_recruitment(); e.show_question(); e.open_answers(0); e.simulate_answers(); e.close_answers()
    assert e.retry_current_question()
    assert e.state == "QUESTION_SHOWN"
    assert len(e.answers) == 0


def test_state_waiter() -> None:
    e = QuizEngineV3()
    base = e.state_version
    seen = []
    def wait() -> None:
        seen.append(e.wait_for_update(base, timeout=1.0))
    t = threading.Thread(target=wait)
    t.start(); time.sleep(0.03); e.enter_practice(); t.join(timeout=1.0)
    assert seen and seen[0] > base


def test_recovery() -> None:
    e = QuizEngineV3(); e.set_questions([Question(prompt="x")]); e.enter_practice(); e.start_recruitment(); e.simulate_join(5); e.close_recruitment()
    e.participants["practice001"].score = 900
    payload = e.recovery_state()
    r = QuizEngineV3(); r.set_questions([Question(prompt="x")]); r.enter_practice()
    assert r.restore_recovery(payload)
    assert len(r.participants) == 5
    assert r.participants["practice001"].score == 900


def test_hot_path_performance() -> None:
    e = QuizEngineV3(); e.set_questions([Question(prompt="x")]); e.set_connected("streamer")
    started = time.perf_counter()
    # Irrelevant normal chat should be extremely cheap and must not dirty the UI state.
    version = e.state_version
    for i in range(1, 50001):
        e.process_chat(i, chat(i, f"u{i % 1000}", "닉", "그냥 채팅"))
    elapsed = time.perf_counter() - started
    assert elapsed < 6.0, f"normal chat path too slow: {elapsed:.3f}s"
    assert e.state_version == version

    e.start_recruitment(); e.simulate_join(200) if e.practice_mode else None
    # Add 500 participants using the actual parser.
    start_seq = e.last_seq + 1
    for i in range(500):
        seq = start_seq + i
        e.process_chat(seq, chat(seq, f"p{i}", f"참가{i}", "!참여"))
    e.close_recruitment(); e.show_question(); e.open_answers(e.last_seq)
    started = time.perf_counter()
    for _ in range(400):
        e.public_state()
    elapsed = time.perf_counter() - started
    assert elapsed < 6.0, f"public state snapshots too slow: {elapsed:.3f}s"


if __name__ == "__main__":
    test_state_and_order()
    test_retry_before_reveal()
    test_state_waiter()
    test_recovery()
    test_hot_path_performance()
    print("quiz-overlay v0.3 tests: PASS")
