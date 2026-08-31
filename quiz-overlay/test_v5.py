from __future__ import annotations

import json
import time

from common import Participant, Question, utc_now
from quiz_engine_v5 import QuizEngineV5
from soop_client_v5 import SoopChatClientV5


def event(uid: str, nick: str, msg: str) -> dict:
    return {"user": {"id": uid, "nickname": nick}, "message": msg, "receivedAt": utc_now().isoformat()}


def basic_flow() -> None:
    q1 = Question(kind="multiple", prompt="2+2?", choices=["3", "4", "5", "6"], answer="2", duration_sec=30, scoring_mode="mixed", first_n=3, base_points=100, rank_points=[30, 20, 10], score_multiplier=2.0)
    q2 = Question(kind="number", prompt="100에 가까운 수", answer="100", duration_sec=30, scoring_mode="all", base_points=100, number_mode="closest", closest_count=2, elimination_mode="first_n", first_n=2)
    e = QuizEngineV5(); e.set_questions([q1, q2]); e.set_connected("tester")
    assert e.start_recruitment()
    for i in range(1, 6): e.process_chat(i, event(f"u{i}", f"닉{i}", "!참여"))
    assert len(e.participants) == 5
    e.process_chat(6, event("u1", "닉1", "안녕하세요"))
    assert e.latest_participant_chat()["message"] == "안녕하세요"
    assert e.close_recruitment(); assert e.show_question()
    e.process_chat(7, event("u1", "닉1", "!2"))
    assert "u1" not in e.answers, "START 이전 답변이 판정되면 안 됨"
    assert e.open_answers(7)
    e.process_chat(8, event("u2", "닉2", "!2")); e.process_chat(9, event("u1", "닉1", "!2")); e.process_chat(10, event("u3", "닉3", "!1"))
    assert list(e.correct_order) == ["u2", "u1"]
    assert e.adjudicate_answer("u3", True)
    assert list(e.correct_order) == ["u2", "u1", "u3"]
    assert e.close_answers(); assert e.reveal_answer()
    assert e.participants["u2"].score == 260  # (100+30)*2
    assert e.participants["u1"].score == 240
    assert e.participants["u3"].score == 220
    assert e.void_current_question(), "정답 공개 후 무효 롤백 가능해야 함"
    assert all(p.score == 0 for p in e.participants.values())
    assert e.next_question(); assert e.show_question(); assert e.open_answers(e.last_seq)
    seq = e.last_seq
    for uid, value in [("u1", "90"), ("u2", "101"), ("u3", "99"), ("u4", "130")]:
        seq += 1; e.process_chat(seq, event(uid, uid, f"!숫자 {value}"))
    assert e.close_answers()
    winners = [r.user_id for r in sorted(e.answers.values(), key=lambda r: (r.rank or 9999, r.seq)) if r.correct]
    assert winners == ["u2", "u3"], winners
    assert e.reveal_answer()
    assert not e.participants["u2"].eliminated and not e.participants["u3"].eliminated
    assert e.participants["u1"].eliminated and e.participants["u4"].eliminated
    assert e.manual_score_adjust("u2", 50, "보너스")
    assert e.participants["u2"].score == 150
    assert e.set_participant_eliminated("u1", False) and not e.participants["u1"].eliminated
    assert e.next_question() and e.state == "FINISHED"


def midjoin_and_feed_bound() -> None:
    e = QuizEngineV5(); e.set_questions([Question(prompt="x", answer="1")]); e.set_connected("tester"); e.start_recruitment()
    for i in range(1, 601):
        e.process_chat(i, event(f"p{i}", f"P{i}", "!참여"))
        e.process_chat(1000+i, event(f"p{i}", f"P{i}", "hello"))
    assert len(e.participant_chat_feed(1000)) == 500
    e.close_recruitment(); e.set_allow_mid_join(True)
    e.process_chat(3000, event("late", "Late", "!참여"))
    assert "late" in e.participants


def performance_hot_path() -> None:
    e = QuizEngineV5(); e.set_questions([Question(prompt="x", answer="1")]); e.set_connected("tester"); e.start_recruitment()
    start = time.perf_counter()
    for i in range(50000): e.process_chat(i + 1, event(f"viewer{i}", "viewer", "ㅋㅋ"))
    elapsed = time.perf_counter() - start
    print(f"50k nonparticipant chat hot path: {elapsed:.3f}s")
    assert elapsed < 8.0, elapsed
    assert len(e.participants) == 0 and e.participant_chat_total == 0


def ranking_load() -> None:
    e = QuizEngineV5()
    for i in range(5000):
        p = Participant(f"id{i}", f"닉{i}", utc_now().isoformat(), correct_count=i % 17, score=(i * 37) % 10000)
        e.participants[p.user_id] = p
    e._bump_score()
    t = time.perf_counter(); a = e.ranking(10); first = time.perf_counter() - t
    t = time.perf_counter(); b = e.ranking(10); second = time.perf_counter() - t
    assert a == b and len(a) == 10
    assert second <= first + 0.02
    print(f"ranking 5k: first={first:.4f}s cached={second:.4f}s")


def queued_client_order() -> None:
    e = QuizEngineV5(); e.set_questions([Question(kind="multiple", prompt="q", choices=["a", "b"], answer="1")]); e.set_connected("tester"); e.start_recruitment()
    c = SoopChatClientV5(e); c._generation = 1
    for seq, msg in [(1, "!참여"), (2, "hello")]:
        frame = {"type": "event", "seq": seq, "event": event("u", "닉", msg)}
        c._on_message(1, None, json.dumps(frame, ensure_ascii=False))
    deadline = time.time() + 2
    while c.processed_event_count < 2 and time.time() < deadline: time.sleep(0.01)
    assert c.processed_event_count == 2
    assert [x["seq"] for x in reversed(e.participant_chat_feed(10))] == [1, 2]
    d = c.diagnostics(); assert d["workerAlive"] and d["queueDrops"] == 0
    c.shutdown()


def main() -> None:
    basic_flow(); midjoin_and_feed_bound(); performance_hot_path(); ranking_load(); queued_client_order()
    print("v0.5 regression/load tests: PASS")


if __name__ == "__main__": main()
