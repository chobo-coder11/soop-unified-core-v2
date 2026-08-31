from __future__ import annotations

import copy
import math
import threading
from collections import deque
from dataclasses import asdict
from typing import Any, Optional

from common import AnswerRecord, Participant, Question, parse_iso, utc_now
from quiz_engine_v4 import QuizEngineV4


class QuizEngineV5(QuizEngineV4):
    """Broadcast-grade v0.5 quiz engine.

    Key properties:
    - only registered participants are retained in the participant chat feed
    - answer ordering is always global downstream seq ordering
    - scoring is reversible for the current question
    - numeric closest-answer and survival/elimination modes
    - manual adjudication and score adjustments without resetting a session
    - state/version notifications remain independent of the desktop renderer
    """

    def __init__(self) -> None:
        super().__init__()
        self.allow_mid_join = False
        self._score_snapshots: dict[int, dict[str, dict[str, Any]]] = {}
        self._void_questions: set[int] = set()
        self._manual_adjustments: deque[dict[str, Any]] = deque(maxlen=200)
        self._score_revision = 1
        self._ranking_cache: dict[tuple[str, int, int], list[dict[str, Any]]] = {}
        self._answer_revision = 1
        self.last_adjudication = ""

    def _bump_score(self) -> None:
        self._score_revision += 1
        self._ranking_cache.clear()

    def set_allow_mid_join(self, enabled: bool) -> None:
        with self.lock:
            enabled = bool(enabled)
            if self.allow_mid_join != enabled:
                self.allow_mid_join = enabled
                self.log(f"중도 참가 {'허용' if enabled else '차단'}")
                self._touch()

    def start_recruitment(self) -> bool:
        with self.lock:
            self._score_snapshots.clear()
            self._void_questions.clear()
            self._manual_adjustments.clear()
            self._bump_score()
        return super().start_recruitment()

    def reset_session(self) -> None:
        with self.lock:
            self._score_snapshots.clear()
            self._void_questions.clear()
            self._manual_adjustments.clear()
            self._bump_score()
        super().reset_session()

    def remove_participant(self, user_id: str) -> bool:
        ok = super().remove_participant(user_id)
        if ok:
            with self.lock:
                self._bump_score()
        return ok

    def _snapshot_scores(self) -> None:
        if self.current_index in self._score_snapshots:
            return
        fields = (
            "correct_count", "score", "streak", "best_streak",
            "total_correct_elapsed_ms", "correct_elapsed_samples",
            "eliminated", "eliminated_round", "first_place_count",
            "top3_count", "last_answer_round",
        )
        self._score_snapshots[self.current_index] = {
            uid: {name: copy.deepcopy(getattr(p, name)) for name in fields}
            for uid, p in self.participants.items()
        }

    def _restore_score_snapshot(self, index: int) -> bool:
        snap = self._score_snapshots.get(index)
        if snap is None:
            return False
        for uid, values in snap.items():
            p = self.participants.get(uid)
            if not p:
                continue
            for name, value in values.items():
                setattr(p, name, copy.deepcopy(value))
        self._last_finalized_index = -1 if self._last_finalized_index == index else self._last_finalized_index
        self._bump_score()
        return True

    def void_current_question(self) -> bool:
        with self.lock:
            if self.state not in {"QUESTION_CLOSED", "ANSWER_REVEALED"}:
                return False
            if self.state == "ANSWER_REVEALED":
                self._restore_score_snapshot(self.current_index)
            self._void_questions.add(self.current_index)
            self.state = "QUESTION_VOID"
            self.overlay_notice = "현재 문제는 무효 처리되었습니다"
            self.last_adjudication = f"Q{self.current_index + 1} 문제 무효"
            self.log(self.last_adjudication)
            self._touch()
            return True

    def next_question(self) -> bool:
        with self.lock:
            if self.state == "QUESTION_VOID":
                if self.current_index + 1 >= len(self.questions):
                    self.state = "FINISHED"
                    self.overlay_notice = "퀴즈 종료 · 최종 순위를 확인하세요"
                else:
                    self.current_index += 1
                    self.state = "LOCKED"
                    self.overlay_notice = f"다음 문제 준비 · Q{self.current_index + 1}"
                self._touch()
                return True
        return super().next_question()

    def manual_score_adjust(self, user_id: str, delta: int, reason: str = "수동 조정") -> bool:
        with self.lock:
            p = self.participants.get(user_id)
            if not p:
                return False
            delta = int(delta)
            p.score += delta
            row = {
                "at": utc_now().isoformat(), "userId": user_id, "display": p.display,
                "delta": delta, "reason": str(reason or "수동 조정")[:120],
            }
            self._manual_adjustments.append(row)
            self.last_adjudication = f"{p.display} {delta:+d}점 · {row['reason']}"
            self.log("점수 조정 · " + self.last_adjudication)
            self._bump_score()
            self._touch()
            return True

    def set_participant_eliminated(self, user_id: str, eliminated: bool) -> bool:
        with self.lock:
            p = self.participants.get(user_id)
            if not p:
                return False
            p.eliminated = bool(eliminated)
            p.eliminated_round = self.current_index + 1 if eliminated else 0
            self.last_adjudication = f"{p.display} {'탈락' if eliminated else '부활'}"
            self.log("참가자 상태 · " + self.last_adjudication)
            self._bump_score()
            self._touch()
            return True

    def adjudicate_answer(self, user_id: str, correct: bool) -> bool:
        with self.lock:
            if self.state not in {"ANSWERING", "QUESTION_CLOSED"}:
                return False
            rec = self.answers.get(user_id)
            if not rec:
                return False
            rec.correct = bool(correct)
            self._rebuild_correct_order()
            self._answer_revision += 1
            self.last_adjudication = f"{rec.nickname}({rec.user_id}) 답변 {'정답' if correct else '오답'} 처리"
            self.log("수동 판정 · " + self.last_adjudication)
            self._touch()
            return True

    def _join_mid_session_if_allowed(self, seq: int, uid: str, nickname: str, message: str) -> bool:
        if message != "!참여" or not self.allow_mid_join or uid in self.participants:
            return False
        if self.state not in {"LOCKED", "QUESTION_SHOWN", "QUESTION_CLOSED", "ANSWER_REVEALED", "QUESTION_VOID"}:
            return False
        self.participants[uid] = Participant(uid, nickname, utc_now().isoformat())
        self.log(f"중도 참가 · {nickname}({uid})")
        self._bump_score()
        return True

    def process_chat(self, seq: int, event: dict[str, Any]) -> None:
        if seq <= 0:
            return
        user = event.get("user") or {}
        uid = str(user.get("id") or "").strip()
        nickname = str(user.get("nickname") or uid or "익명").strip()
        message = str(event.get("message") or "").strip()
        if not uid or not message:
            return

        with self.lock:
            if seq in self._seen_seqs:
                return
            self._seen_seqs.add(seq)
            self.last_seq = max(self.last_seq, seq)
            if len(self._seen_seqs) > 24000:
                floor = max(0, self.last_seq - 12000)
                self._seen_seqs = {s for s in self._seen_seqs if s >= floor}

            was_participant = uid in self.participants
            state_before = self.state
            question_before = self.current_index
            joined_mid = self._join_mid_session_if_allowed(seq, uid, nickname, message)

            joined = False
            cancelled = False
            if self.state == "RECRUITING":
                if message == "!참여":
                    existing = self.participants.get(uid)
                    if existing:
                        existing.nickname = nickname
                    else:
                        self.participants[uid] = Participant(uid, nickname, utc_now().isoformat())
                        self.log(f"참가 · {nickname}({uid})")
                        self._bump_score()
                        joined = True
                    self._touch()
                elif message == "!취소" and uid in self.participants:
                    self.participants.pop(uid, None)
                    self.answers.pop(uid, None)
                    self.log(f"참가 취소 · {nickname}({uid})")
                    self._bump_score()
                    cancelled = True
                    self._touch()

            is_participant = uid in self.participants
            accepted_answer = False
            answer: Optional[AnswerRecord] = None

            if self.state == "ANSWERING" and is_participant and seq > self.answer_gate_seq:
                q = self.current_question
                p = self.participants.get(uid)
                if q and p and (not p.eliminated or q.allow_eliminated_answers):
                    parsed = self._parse_answer(q, message)
                    if parsed is not None:
                        previous = self.answers.get(uid)
                        if not (previous and q.answer_policy == "first"):
                            # Closest-number questions decide correctness after the round closes.
                            correct = False if q.kind == "number" and q.number_mode == "closest" else self._is_correct(q, parsed)
                            received = parse_iso(event.get("receivedAt")) or utc_now()
                            elapsed_ms = 0
                            if self.answer_opened_at:
                                elapsed_ms = max(0, int((received - self.answer_opened_at).total_seconds() * 1000))
                            answer = AnswerRecord(uid, nickname, message, parsed, seq, received.isoformat(), elapsed_ms, correct)
                            self.answers[uid] = answer
                            p.nickname = nickname
                            p.last_answer_round = self.current_index + 1
                            self._rebuild_correct_order()
                            self._answer_revision += 1
                            accepted_answer = True
                            self._touch()
                            if q.auto_close_quota and q.number_mode != "closest" and q.scoring_mode in {"first_n", "mixed"} and len(self.correct_order) >= q.first_n:
                                if self._close_answers_locked(auto=True):
                                    self._touch()

            # Track participant chat independently of answer scoring.
            is_participant = uid in self.participants
            if was_participant or is_participant or cancelled:
                received = parse_iso(event.get("receivedAt")) or utc_now()
                row = {
                    "seq": seq,
                    "userId": uid,
                    "nickname": nickname,
                    "display": f"{nickname}({uid})",
                    "message": message,
                    "receivedAt": received.isoformat(),
                    "state": state_before,
                    "questionIndex": question_before,
                    "isAnswer": accepted_answer,
                    "accepted": accepted_answer,
                    "normalizedAnswer": answer.normalized_answer if accepted_answer and answer else None,
                    "correct": answer.correct if accepted_answer and answer else None,
                    "cancelled": cancelled,
                    "joined": joined or joined_mid,
                }
                self._participant_chat.append(row)
                self.participant_chat_total += 1
                self._touch_chat()

    def _prepare_closest_answers(self) -> None:
        q = self.current_question
        if not q or q.kind != "number" or q.number_mode != "closest":
            return
        try:
            target = float(q.answer)
        except Exception:
            return
        numeric: list[tuple[float, int, AnswerRecord]] = []
        for rec in self.answers.values():
            try:
                distance = abs(float(rec.normalized_answer) - target)
            except Exception:
                continue
            numeric.append((distance, rec.seq, rec))
        numeric.sort(key=lambda x: (x[0], x[1]))
        winners = {rec.user_id for _, _, rec in numeric[: max(1, q.closest_count)]}
        for rec in self.answers.values():
            rec.correct = rec.user_id in winners
        self._rebuild_correct_order_by_closest(numeric)

    def _rebuild_correct_order_by_closest(self, numeric: list[tuple[float, int, AnswerRecord]]) -> None:
        self.correct_order = []
        for rec in self.answers.values():
            rec.rank = None
        rank = 0
        for _distance, _seq, rec in numeric:
            if not rec.correct:
                continue
            rank += 1
            rec.rank = rank
            self.correct_order.append(rec.user_id)

    def close_answers(self, auto: bool = False) -> bool:
        with self.lock:
            if self.state != "ANSWERING":
                return False
            self._prepare_closest_answers()
            ok = self._close_answers_locked(auto=auto)
            if ok:
                self._touch()
            return ok

    def reveal_answer(self) -> bool:
        with self.lock:
            if self.state != "QUESTION_CLOSED":
                return False
            self._prepare_closest_answers()
        return super().reveal_answer()

    def _start_timer(self, seconds: int, generation: int) -> None:
        # Override only the closing edge so closest-number scoring is prepared.
        def run() -> None:
            import time
            deadline = time.monotonic() + max(1, seconds)
            while time.monotonic() < deadline:
                time.sleep(0.15)
                with self.lock:
                    if self.state != "ANSWERING" or generation != self._timer_generation:
                        return
            with self.lock:
                if self.state == "ANSWERING" and generation == self._timer_generation:
                    self._prepare_closest_answers()
                    self._close_answers_locked(auto=True)
                    self._touch()
        threading.Thread(target=run, daemon=True, name=f"quiz-timer-v5-{generation}").start()

    def _finalize_scores(self) -> None:
        if self._last_finalized_index == self.current_index or self.current_index in self._void_questions:
            return
        q = self.current_question
        if not q:
            return
        self._prepare_closest_answers()
        self._snapshot_scores()
        if q.kind == "number" and q.number_mode == "closest":
            correct_records = sorted((a for a in self.answers.values() if a.correct), key=lambda a: (a.rank or 999999, a.seq))
        else:
            correct_records = sorted((a for a in self.answers.values() if a.correct), key=lambda a: a.seq)
        correct_ids = {a.user_id for a in correct_records}
        multiplier = max(0.0, float(q.score_multiplier or 1.0))
        for i, record in enumerate(correct_records):
            participant = self.participants.get(record.user_id)
            if not participant:
                continue
            participant.correct_count += 1
            participant.streak += 1
            participant.best_streak = max(participant.best_streak, participant.streak)
            participant.total_correct_elapsed_ms += max(0, record.elapsed_ms)
            participant.correct_elapsed_samples += 1
            if i == 0:
                participant.first_place_count += 1
            if i < 3:
                participant.top3_count += 1
            base = int(round(q.base_points * multiplier))
            if q.scoring_mode == "all":
                participant.score += base
            elif q.scoring_mode == "first_n":
                if i < q.first_n:
                    raw = q.rank_points[i] if i < len(q.rank_points) else q.base_points
                    participant.score += int(round(raw * multiplier))
            elif q.scoring_mode == "mixed":
                participant.score += base
                if i < q.first_n:
                    raw = q.rank_points[i] if i < len(q.rank_points) else 0
                    participant.score += int(round(raw * multiplier))
            else:
                participant.score += base

        for uid, participant in self.participants.items():
            if uid not in correct_ids:
                participant.streak = 0

        if q.elimination_mode == "wrong":
            for uid, participant in self.participants.items():
                if uid not in correct_ids and not participant.eliminated:
                    participant.eliminated = True
                    participant.eliminated_round = self.current_index + 1
        elif q.elimination_mode == "first_n":
            survivors = {r.user_id for r in correct_records[: max(1, q.first_n)]}
            for uid, participant in self.participants.items():
                if uid not in survivors and not participant.eliminated:
                    participant.eliminated = True
                    participant.eliminated_round = self.current_index + 1

        self._last_finalized_index = self.current_index
        self._bump_score()

    def ranking(self, limit: int = 10) -> list[dict[str, Any]]:
        with self.lock:
            limit = max(1, limit)
            key = (self.ranking_mode, limit, self._score_revision)
            cached = self._ranking_cache.get(key)
            if cached is not None:
                return copy.deepcopy(cached)
            rows = list(self.participants.values())
            if self.ranking_mode == "score":
                rows.sort(key=lambda p: (-p.score, -p.correct_count, p.total_correct_elapsed_ms, p.joined_at, p.user_id))
            elif self.ranking_mode == "streak":
                rows.sort(key=lambda p: (-p.best_streak, -p.correct_count, -p.score, p.joined_at, p.user_id))
            else:
                rows.sort(key=lambda p: (-p.correct_count, -p.score, p.total_correct_elapsed_ms, p.joined_at, p.user_id))
            output = []
            for rank, p in enumerate(rows[:limit], start=1):
                avg = int(p.total_correct_elapsed_ms / p.correct_elapsed_samples) if p.correct_elapsed_samples else None
                output.append({
                    "rank": rank, "userId": p.user_id, "nickname": p.nickname, "display": p.display,
                    "correct": p.correct_count, "score": p.score, "streak": p.best_streak, "avgMs": avg,
                    "eliminated": p.eliminated, "firstPlace": p.first_place_count, "top3": p.top3_count,
                })
            self._ranking_cache[key] = copy.deepcopy(output)
            return output

    def answer_distribution(self) -> list[dict[str, Any]]:
        with self.lock:
            q = self.current_question
            if not q:
                return []
            counts: dict[str, int] = {}
            for rec in self.answers.values():
                counts[rec.normalized_answer] = counts.get(rec.normalized_answer, 0) + 1
            if q.kind == "multiple":
                return [{"answer": str(i + 1), "label": label, "count": counts.get(str(i + 1), 0)} for i, label in enumerate(q.choices)]
            if q.kind == "ox":
                return [{"answer": v, "label": v, "count": counts.get(v, 0)} for v in ("O", "X")]
            return sorted(({"answer": k, "label": k, "count": v} for k, v in counts.items()), key=lambda x: (-x["count"], x["answer"]))[:20]

    def public_state(self) -> dict[str, Any]:
        state = super().public_state()
        with self.lock:
            state["allowMidJoin"] = self.allow_mid_join
            state["survivors"] = sum(1 for p in self.participants.values() if not p.eliminated)
            state["eliminated"] = sum(1 for p in self.participants.values() if p.eliminated)
            state["voidQuestion"] = self.current_index in self._void_questions or self.state == "QUESTION_VOID"
            state["lastAdjudication"] = self.last_adjudication
            state["answerDistribution"] = self.answer_distribution()
            state["manualAdjustments"] = list(self._manual_adjustments)[-10:]
            return state

    def recovery_state(self) -> dict[str, Any]:
        base = super().recovery_state()
        with self.lock:
            base["allowMidJoin"] = self.allow_mid_join
            base["voidQuestions"] = sorted(self._void_questions)
            base["manualAdjustments"] = list(self._manual_adjustments)
            return base

    def restore_recovery(self, payload: dict[str, Any]) -> bool:
        ok = super().restore_recovery(payload)
        if not ok:
            return False
        with self.lock:
            self.allow_mid_join = bool(payload.get("allowMidJoin", False))
            self._void_questions = {int(x) for x in payload.get("voidQuestions", []) if isinstance(x, int) or str(x).isdigit()}
            self._manual_adjustments.clear()
            for row in payload.get("manualAdjustments", [])[-200:]:
                if isinstance(row, dict):
                    self._manual_adjustments.append(dict(row))
            self._bump_score()
            self._touch()
        return True
