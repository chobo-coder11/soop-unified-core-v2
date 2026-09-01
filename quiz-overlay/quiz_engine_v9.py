from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from quiz_engine_v8 import QuizEngineV8


UI_VERSION = "0.9.0"
PRODUCT_NAME = "SOOP Quiz Studio"


class QuizEngineV9(QuizEngineV8):
    """Hardened public state + question transition rules for v0.9.

    Important separation:
    - the desktop controller keeps the full question and scoring data;
    - browser overlays only receive display-safe fields;
    - answer/correctness data is published only after ANSWER_REVEALED.
    """

    def __init__(self) -> None:
        super().__init__()
        self.last_transition_error = ""
        self.question_shown_monotonic = 0.0

    def current_question_error(self) -> str:
        with self.lock:
            q = self.current_question
            if not q:
                return "공개할 문제가 없습니다. 문제 편집에서 문제를 먼저 추가해주세요."
            if not str(q.prompt or "").strip():
                return "문제 내용이 비어 있습니다. 문제 문장을 입력해주세요."
            if q.kind == "multiple":
                if len(q.choices) < 2:
                    return "객관식 문제는 보기가 최소 2개 필요합니다."
                if any(not str(choice).strip() for choice in q.choices):
                    return "객관식 보기에 빈 항목이 있습니다. 빈 보기를 채우거나 삭제해주세요."
                try:
                    answer_index = int(str(q.answer).strip())
                except Exception:
                    return "객관식 정답 번호가 올바르지 않습니다."
                if answer_index < 1 or answer_index > len(q.choices):
                    return f"객관식 정답은 1~{len(q.choices)}번 중 하나여야 합니다."
            elif q.kind == "ox":
                if str(q.answer).strip().upper() not in {"O", "X"}:
                    return "OX 문제의 정답은 O 또는 X여야 합니다."
            elif q.kind == "short":
                if not str(q.answer or "").strip():
                    return "주관식 정답이 비어 있습니다."
            elif q.kind == "number":
                try:
                    float(str(q.answer).strip())
                except Exception:
                    return "숫자 문제의 정답은 숫자로 입력해주세요."
            else:
                return f"지원하지 않는 문제 유형입니다: {q.kind}"
            if int(q.duration_sec or 0) < 1:
                return "답변 시간이 1초보다 짧습니다."
            return ""

    def close_recruitment(self) -> bool:
        with self.lock:
            if self.state != "RECRUITING":
                self.last_transition_error = "현재 단계에서는 참가 모집을 마감할 수 없습니다."
                return False
            if not self.questions:
                self.last_transition_error = "문제가 하나도 없어 참가 모집을 마감할 수 없습니다."
                return False
            self.last_transition_error = ""
        return super().close_recruitment()

    def show_question(self) -> bool:
        # v0.3 allowed QUESTION_CLOSED / ANSWER_REVEALED here. That made it
        # possible to clear answers and re-show the same round by mistake.
        with self.lock:
            if self.state != "LOCKED":
                self.last_transition_error = "문제 공개는 '문제 준비' 단계에서만 가능합니다."
                return False
            error = self.current_question_error()
            if error:
                self.last_transition_error = error
                return False
            self.last_transition_error = ""
            ok = super().show_question()
            if ok:
                self.question_shown_monotonic = time.monotonic()
            return ok

    def retry_current_question(self) -> bool:
        ok = super().retry_current_question()
        if ok:
            with self.lock:
                self.question_shown_monotonic = time.monotonic()
                self.last_transition_error = ""
        return ok

    def open_answers(self, gate_seq: int | None = None) -> bool:
        with self.lock:
            if self.state != "QUESTION_SHOWN":
                self.last_transition_error = "START는 문제가 공개된 뒤에만 가능합니다."
                return False
            error = self.current_question_error()
            if error:
                self.last_transition_error = error
                return False
            if not self.connected:
                self.last_transition_error = "방송 채팅 연결이 끊겨 START할 수 없습니다. 연결 상태를 확인해주세요."
                return False
            self.last_transition_error = ""
        return super().open_answers(gate_seq)

    def reveal_answer(self) -> bool:
        ok = super().reveal_answer()
        with self.lock:
            self.last_transition_error = "" if ok else "답변 마감 후에만 정답을 공개할 수 있습니다."
        return ok

    def next_question(self) -> bool:
        ok = super().next_question()
        with self.lock:
            self.last_transition_error = "" if ok else "정답 공개 또는 문제 무효 처리 후 다음 문제로 이동할 수 있습니다."
        return ok

    def _public_question(self) -> dict[str, Any] | None:
        q = self.current_question
        if not q:
            return None
        public: dict[str, Any] = {
            "kind": str(q.kind),
            "prompt": str(q.prompt),
            "choices": [str(x) for x in q.choices],
            "duration_sec": int(q.duration_sec),
        }
        # The answer is intentionally absent until the reveal state.
        if self.state == "ANSWER_REVEALED":
            public["answer"] = str(q.answer)
            public["number_mode"] = str(q.number_mode)
            public["score_multiplier"] = float(q.score_multiplier or 1.0)
        return public

    def _question_key(self, public_question: dict[str, Any] | None) -> str:
        if not public_question:
            return "none"
        raw = json.dumps(public_question, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.blake2s(raw.encode("utf-8"), digest_size=8).hexdigest()

    def public_state(self) -> dict[str, Any]:
        # Do not call the legacy public_state here: it serializes the complete
        # Question dataclass (answer, aliases, scoring internals) and repeatedly
        # sorts all correct answers while ANSWERING. Build the overlay payload
        # directly from already-maintained engine structures instead.
        with self.lock:
            q_public = self._public_question()
            revealed = self.state == "ANSWER_REVEALED"
            first_correct: list[dict[str, Any]] = []
            if revealed:
                for uid in self.correct_order[:10]:
                    rec = self.answers.get(uid)
                    if not rec:
                        continue
                    first_correct.append({
                        "rank": rec.rank,
                        "userId": rec.user_id,
                        "display": f"{rec.nickname}({rec.user_id})",
                        "elapsedMs": max(0, int(rec.elapsed_ms)),
                    })

            remaining_ms = None
            if self.state == "ANSWERING" and self.timer_deadline_monotonic is not None:
                remaining_ms = max(0, int((self.timer_deadline_monotonic - time.monotonic()) * 1000))

            survivors = sum(1 for p in self.participants.values() if not p.eliminated)
            eliminated = len(self.participants) - survivors
            state: dict[str, Any] = {
                "app": {"name": PRODUCT_NAME, "version": UI_VERSION},
                "schemaVersion": 2,
                "stateVersion": int(self.state_version),
                "state": str(self.state),
                "connected": bool(self.connected),
                "practice": bool(self.practice_mode),
                "streamerId": str(self.streamer_id),
                "participants": len(self.participants),
                "answered": len(self.answers),
                "correct": len(self.correct_order) if revealed else 0,
                "questionIndex": int(self.current_index),
                "questionCount": len(self.questions),
                "question": q_public,
                "questionKey": self._question_key(q_public),
                "remainingMs": remaining_ms,
                "deadlineEpochMs": self.answer_deadline_epoch_ms if self.state == "ANSWERING" else None,
                "notice": str(self.overlay_notice or ""),
                "integrityWarning": str(self.integrity_warning or ""),
                "firstCorrect": first_correct,
                "rankingMode": str(self.ranking_mode),
                "ranking": self.ranking(10),
                "answerHint": self.answer_hint(),
                "visual": dict(self.visual),
                "allowMidJoin": bool(self.allow_mid_join),
                "survivors": survivors,
                "eliminated": eliminated,
                "voidQuestion": self.current_index in self._void_questions or self.state == "QUESTION_VOID",
                "transitionError": str(self.last_transition_error or ""),
            }
            # Distribution is only useful after the result is public. Avoid an
            # O(n) rebuild for every incoming answer and avoid leaking live data.
            state["answerDistribution"] = self.answer_distribution() if revealed else []
            return state
