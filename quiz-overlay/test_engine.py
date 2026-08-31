from __future__ import annotations

from common import Question, utc_now
from engine import QuizEngine


def chat(engine: QuizEngine, seq: int, uid: str, nick: str, message: str) -> None:
    engine.process_chat(seq, {
        "category": "chat",
        "type": "CHAT_MESSAGE",
        "user": {"id": uid, "nickname": nick},
        "message": message,
        "receivedAt": utc_now().isoformat(),
    })


def prepared(question: Question) -> QuizEngine:
    e = QuizEngine()
    e.questions = [question]
    e.set_connected("streamer")
    assert e.start_recruitment()
    chat(e, 1, "u1", "고래팬", "!참여")
    chat(e, 2, "u2", "감자맨", "!참여")
    chat(e, 3, "u3", "울치원", "!참여")
    assert len(e.participants) == 3
    assert e.close_recruitment()
    assert e.show_question()
    return e


def test_multiple_first_n() -> None:
    e = prepared(Question(kind="multiple", prompt="2+2?", choices=["3", "4", "5", "6"], answer="2", scoring_mode="first_n", first_n=3, rank_points=[300, 200, 100], auto_close_time=False))
    chat(e, 10, "u1", "고래팬", "!2")
    assert not e.answers, "START 전 답변이 기록되면 안 됨"
    assert e.open_answers()
    gate = e.answer_gate_seq
    chat(e, gate + 1, "outsider", "비참가", "!2")
    assert not e.answers, "비참가자 답변은 무시해야 함"
    chat(e, gate + 2, "u2", "감자맨", "!2")
    chat(e, gate + 4, "u1", "고래팬", "!2")
    chat(e, gate + 3, "u3", "울치원", "!2")
    assert e.correct_order == ["u2", "u3", "u1"], "선착순은 global seq 순서여야 함"
    assert e.close_answers()
    assert e.reveal_answer()
    assert [e.participants[x].score for x in ["u2", "u3", "u1"]] == [300, 200, 100]


def test_short_normalization() -> None:
    e = prepared(Question(kind="short", prompt="수도?", answer="서울특별시", accepted_answers=["서울"], auto_close_time=False))
    assert e.open_answers(); g = e.answer_gate_seq
    chat(e, g + 1, "u1", "고래팬", "!정답 서 울")
    assert e.answers["u1"].correct


def test_ox_and_number() -> None:
    e = prepared(Question(kind="ox", prompt="정답 O", answer="O", auto_close_time=False))
    assert e.open_answers(); g = e.answer_gate_seq
    chat(e, g + 1, "u1", "고래팬", "!O")
    assert e.answers["u1"].correct

    n = prepared(Question(kind="number", prompt="100 근처", answer="100", number_tolerance=2, auto_close_time=False))
    assert n.open_answers(); g = n.answer_gate_seq
    chat(n, g + 1, "u1", "고래팬", "!숫자 101.5")
    assert n.answers["u1"].correct


def test_disconnect_safety() -> None:
    e = prepared(Question(kind="multiple", prompt="x", choices=["a", "b"], answer="1", auto_close_time=False))
    assert e.open_answers()
    e.set_disconnected("test")
    assert e.state == "QUESTION_CLOSED"
    assert e.integrity_warning


if __name__ == "__main__":
    test_multiple_first_n()
    test_short_normalization()
    test_ox_and_number()
    test_disconnect_safety()
    print("quiz-overlay engine tests: PASS")
