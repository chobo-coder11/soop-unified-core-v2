from __future__ import annotations

from common import Question, utc_now
from quiz_engine import QuizEngine


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


def test_recruitment_filters_and_display() -> None:
    e = QuizEngine(); e.questions = [Question(prompt="x")]; e.set_connected("s"); assert e.start_recruitment()
    chat(e, 1, "a", "같은닉", "안녕하세요")
    assert not e.participants
    chat(e, 2, "a", "같은닉", "!참여")
    chat(e, 3, "b", "같은닉", "!참여")
    assert e.participants["a"].display == "같은닉(a)"
    assert e.participants["b"].display == "같은닉(b)"
    chat(e, 4, "a", "같은닉", "!취소")
    assert "a" not in e.participants


def test_multiple_first_n_global_seq() -> None:
    e = prepared(Question(kind="multiple", prompt="2+2?", choices=["3", "4", "5", "6"], answer="2", scoring_mode="first_n", first_n=3, rank_points=[300, 200, 100], auto_close_time=False))
    chat(e, 10, "u1", "고래팬", "!2")
    assert not e.answers, "START 전 답변이 기록되면 안 됨"
    assert e.open_answers(gate_seq=50)
    chat(e, 49, "u1", "고래팬", "!2")
    chat(e, 50, "u2", "감자맨", "!2")
    assert not e.answers, "START gate 이하 seq는 무시해야 함"
    chat(e, 51, "outsider", "비참가", "!2")
    assert not e.answers, "비참가자 답변은 무시해야 함"
    chat(e, 54, "u1", "고래팬", "!2")
    chat(e, 52, "u2", "감자맨", "!2")
    chat(e, 53, "u3", "울치원", "!2")
    assert e.correct_order == ["u2", "u3", "u1"], "선착순은 global seq 순서여야 함"
    assert e.close_answers(); assert e.reveal_answer()
    assert [e.participants[x].score for x in ["u2", "u3", "u1"]] == [300, 200, 100]


def test_last_answer_policy_reorders_by_final_answer_seq() -> None:
    e = prepared(Question(kind="multiple", prompt="정답 2", choices=["a", "b"], answer="2", answer_policy="last", auto_close_time=False))
    assert e.open_answers(gate_seq=10)
    chat(e, 11, "u1", "고래팬", "!2")
    chat(e, 12, "u2", "감자맨", "!2")
    chat(e, 13, "u1", "고래팬", "!1")
    assert e.correct_order == ["u2"]
    chat(e, 14, "u1", "고래팬", "!2")
    assert e.correct_order == ["u2", "u1"], "마지막 답변 인정이면 최종 정답 입력 seq가 순위 기준"


def test_short_normalization() -> None:
    e = prepared(Question(kind="short", prompt="수도?", answer="서울특별시", accepted_answers=["서울"], auto_close_time=False))
    assert e.open_answers(gate_seq=10)
    chat(e, 11, "u1", "고래팬", "!정답 서 울")
    assert e.answers["u1"].correct


def test_ox_and_number() -> None:
    e = prepared(Question(kind="ox", prompt="정답 O", answer="O", auto_close_time=False))
    assert e.open_answers(gate_seq=10); chat(e, 11, "u1", "고래팬", "!O"); assert e.answers["u1"].correct
    n = prepared(Question(kind="number", prompt="100 근처", answer="100", number_tolerance=2, auto_close_time=False))
    assert n.open_answers(gate_seq=10); chat(n, 11, "u1", "고래팬", "!숫자 101.5"); assert n.answers["u1"].correct


def test_gap_and_disconnect_safety() -> None:
    e = prepared(Question(kind="multiple", prompt="x", choices=["a", "b"], answer="1", auto_close_time=False))
    assert e.open_answers(gate_seq=10)
    e.on_gap({"fromSeq": 11, "toSeq": 13})
    assert e.state == "QUESTION_CLOSED" and e.integrity_warning
    e2 = prepared(Question(kind="multiple", prompt="x", choices=["a", "b"], answer="1", auto_close_time=False))
    assert e2.open_answers(gate_seq=10)
    e2.set_disconnected("test")
    assert e2.state == "QUESTION_CLOSED" and e2.integrity_warning


def test_manual_transition_contract() -> None:
    e = prepared(Question(kind="multiple", prompt="x", choices=["a", "b"], answer="1", auto_close_time=False))
    assert e.state == "QUESTION_SHOWN"
    assert e.open_answers(gate_seq=10)
    chat(e, 11, "u1", "고래팬", "!1")
    assert e.state == "ANSWERING", "정답자가 나와도 자동으로 정답 공개 단계로 넘어가면 안 됨"
    assert e.close_answers(); assert e.state == "QUESTION_CLOSED"
    assert e.reveal_answer(); assert e.state == "ANSWER_REVEALED"
    assert e.next_question(); assert e.state == "FINISHED"


if __name__ == "__main__":
    test_recruitment_filters_and_display()
    test_multiple_first_n_global_seq()
    test_last_answer_policy_reorders_by_final_answer_seq()
    test_short_normalization()
    test_ox_and_number()
    test_gap_and_disconnect_safety()
    test_manual_transition_contract()
    print("quiz-overlay v0.2 engine tests: PASS")
