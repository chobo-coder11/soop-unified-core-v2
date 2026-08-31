from __future__ import annotations

import re
import string
import threading
import time
import unicodedata
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Optional

from common import APP_NAME, APP_VERSION, AnswerRecord, Participant, Question, parse_iso, utc_now


class QuizEngine:
    """Thread-safe quiz state machine.

    Accuracy rules:
    - only registered participant IDs are eligible after recruitment closes
    - answers are accepted only while state == ANSWERING
    - a server global sequence gate is captured at START
    - ranking order is global sequence order, not client render time
    - a WebSocket gap during ANSWERING closes the round and raises an integrity warning
    """

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.state = "DISCONNECTED"
        self.connected = False
        self.streamer_id = ""
        self.questions: list[Question] = []
        self.current_index = 0
        self.participants: dict[str, Participant] = {}
        self.answers: dict[str, AnswerRecord] = {}
        self.correct_order: list[str] = []
        self.last_seq = 0
        self.answer_gate_seq = 0
        self.answer_opened_at: Optional[datetime] = None
        self.integrity_warning = ""
        self.last_gap: Optional[dict[str, Any]] = None
        self.overlay_notice = ""
        self.timer_deadline_monotonic: Optional[float] = None
        self.timer_thread: Optional[threading.Thread] = None
        self.event_log: list[str] = []
        self._seen_seqs: set[int] = set()
        self._last_finalized_index = -1
        self.ranking_mode = "correct_count"
        self.visual: dict[str, Any] = {
            "theme": "dark",
            "motion": True,
            "compactRanking": False,
            "showFastest": True,
        }

    @property
    def current_question(self) -> Optional[Question]:
        if not self.questions or self.current_index < 0 or self.current_index >= len(self.questions):
            return None
        return self.questions[self.current_index]

    def log(self, text: str) -> None:
        with self.lock:
            stamp = datetime.now().strftime("%H:%M:%S")
            self.event_log.append(f"[{stamp}] {text}")
            self.event_log = self.event_log[-250:]

    def set_connected(self, streamer_id: str) -> None:
        with self.lock:
            self.connected = True
            self.streamer_id = streamer_id
            if self.state == "DISCONNECTED":
                self.state = "READY"
            self.log(f"방송 채팅 연결됨 · {streamer_id}")

    def set_disconnected(self, reason: str = "") -> None:
        with self.lock:
            self.connected = False
            if self.state == "ANSWERING":
                self._close_for_integrity("답변 접수 중 연결이 끊겨 문제를 안전하게 마감했습니다. 이 문제는 재진행을 권장합니다.")
            elif self.state == "READY":
                self.state = "DISCONNECTED"
            if reason:
                self.log(f"방송 채팅 연결 종료 · {reason}")

    def on_gap(self, gap: dict[str, Any]) -> None:
        with self.lock:
            self.last_gap = dict(gap)
            self.integrity_warning = "실시간 채팅 일부가 누락될 가능성이 감지되었습니다."
            self.log(f"실시간 무결성 경고 · seq {gap.get('fromSeq')}~{gap.get('toSeq')}")
            if self.state == "ANSWERING":
                self._close_for_integrity("답변 접수 중 채팅 누락 가능성이 감지되어 자동 마감했습니다. 공정성을 위해 문제 재진행을 권장합니다.")

    def _close_for_integrity(self, warning: str) -> None:
        self.state = "QUESTION_CLOSED"
        self.timer_deadline_monotonic = None
        self.integrity_warning = warning
        self.overlay_notice = "연결 문제로 답변 접수가 중단되었습니다"

    def set_visual(self, *, theme: Optional[str] = None, motion: Optional[bool] = None, compact_ranking: Optional[bool] = None, show_fastest: Optional[bool] = None) -> None:
        with self.lock:
            if theme in {"dark", "light"}:
                self.visual["theme"] = theme
            if motion is not None:
                self.visual["motion"] = bool(motion)
            if compact_ranking is not None:
                self.visual["compactRanking"] = bool(compact_ranking)
            if show_fastest is not None:
                self.visual["showFastest"] = bool(show_fastest)

    def start_recruitment(self) -> bool:
        with self.lock:
            if not self.connected or self.state not in {"READY", "LOCKED", "FINISHED"}:
                return False
            self.participants.clear()
            self.answers.clear()
            self.correct_order.clear()
            self.current_index = 0
            self._last_finalized_index = -1
            self.integrity_warning = ""
            self.last_gap = None
            self.state = "RECRUITING"
            self.overlay_notice = "채팅에 !참여 를 입력하세요"
            self.log("참가 모집 시작")
            return True

    def close_recruitment(self) -> bool:
        with self.lock:
            if self.state != "RECRUITING":
                return False
            self.state = "LOCKED"
            self.overlay_notice = f"참가 마감 · 총 {len(self.participants)}명"
            self.log(f"참가 모집 마감 · {len(self.participants)}명")
            return True

    def show_question(self) -> bool:
        with self.lock:
            q = self.current_question
            if not q or self.state not in {"LOCKED", "ANSWER_REVEALED", "QUESTION_CLOSED"}:
                return False
            self.answers.clear()
            self.correct_order.clear()
            self.answer_opened_at = None
            self.timer_deadline_monotonic = None
            self.integrity_warning = ""
            self.state = "QUESTION_SHOWN"
            self.overlay_notice = "문제를 확인해주세요 · 아직 답변은 받지 않습니다"
            self.log(f"Q{self.current_index + 1} 문제 공개")
            return True

    def open_answers(self, gate_seq: Optional[int] = None) -> bool:
        with self.lock:
            q = self.current_question
            if not q or not self.connected or self.state != "QUESTION_SHOWN":
                return False
            self.answer_gate_seq = max(self.last_seq, int(gate_seq or 0))
            self.answer_opened_at = utc_now()
            self.state = "ANSWERING"
            self.overlay_notice = "START! 정답을 입력해주세요"
            self.timer_deadline_monotonic = time.monotonic() + max(1, q.duration_sec)
            self.log(f"Q{self.current_index + 1} 답변 시작 · gate seq={self.answer_gate_seq}")
            if q.auto_close_time:
                self._start_timer(q.duration_sec)
            return True

    def _start_timer(self, seconds: int) -> None:
        def run() -> None:
            deadline = time.monotonic() + max(1, seconds)
            while time.monotonic() < deadline:
                time.sleep(0.08)
                with self.lock:
                    if self.state != "ANSWERING":
                        return
            self.close_answers(auto=True)

        self.timer_thread = threading.Thread(target=run, daemon=True)
        self.timer_thread.start()

    def close_answers(self, auto: bool = False) -> bool:
        with self.lock:
            if self.state != "ANSWERING":
                return False
            self.state = "QUESTION_CLOSED"
            self.timer_deadline_monotonic = None
            self.overlay_notice = "정답 입력이 마감되었습니다"
            self.log(f"답변 마감{' · 자동' if auto else ''} · {len(self.answers)}명")
            return True

    def reveal_answer(self) -> bool:
        with self.lock:
            if self.state != "QUESTION_CLOSED":
                return False
            self._finalize_scores()
            self.state = "ANSWER_REVEALED"
            self.overlay_notice = "정답 공개"
            self.log(f"Q{self.current_index + 1} 정답 공개")
            return True

    def next_question(self) -> bool:
        with self.lock:
            if self.state != "ANSWER_REVEALED":
                return False
            if self.current_index + 1 >= len(self.questions):
                self.state = "FINISHED"
                self.overlay_notice = "퀴즈 종료 · 최종 순위를 확인하세요"
                self.log("퀴즈 종료")
                return True
            self.current_index += 1
            self.state = "LOCKED"
            self.overlay_notice = f"다음 문제 준비 · Q{self.current_index + 1}"
            self.log(f"Q{self.current_index + 1} 준비")
            return True

    def reset_session(self) -> None:
        with self.lock:
            self.participants.clear()
            self.answers.clear()
            self.correct_order.clear()
            self.current_index = 0
            self.answer_gate_seq = self.last_seq
            self._last_finalized_index = -1
            self.integrity_warning = ""
            self.last_gap = None
            self.state = "READY" if self.connected else "DISCONNECTED"
            self.overlay_notice = ""
            self.log("세션 초기화")

    def process_chat(self, seq: int, event: dict[str, Any]) -> None:
        with self.lock:
            if seq <= 0 or seq in self._seen_seqs:
                return
            self._seen_seqs.add(seq)
            self.last_seq = max(self.last_seq, seq)
            if len(self._seen_seqs) > 12000:
                floor = max(0, self.last_seq - 6000)
                self._seen_seqs = {s for s in self._seen_seqs if s >= floor}

            user = event.get("user") or {}
            uid = str(user.get("id") or "").strip()
            nickname = str(user.get("nickname") or uid or "익명").strip()
            message = str(event.get("message") or "").strip()
            if not uid or not message:
                return

            if self.state == "RECRUITING":
                if message == "!참여":
                    existing = self.participants.get(uid)
                    if existing:
                        existing.nickname = nickname
                    else:
                        self.participants[uid] = Participant(uid, nickname, utc_now().isoformat())
                        self.log(f"참가 · {nickname}({uid})")
                    return
                if message == "!취소" and uid in self.participants:
                    self.participants.pop(uid, None)
                    self.log(f"참가 취소 · {nickname}({uid})")
                return

            if self.state != "ANSWERING" or uid not in self.participants or seq <= self.answer_gate_seq:
                return

            q = self.current_question
            if not q:
                return
            parsed = self._parse_answer(q, message)
            if parsed is None:
                return

            previous = self.answers.get(uid)
            if previous and q.answer_policy == "first":
                return

            correct = self._is_correct(q, parsed)
            received = parse_iso(event.get("receivedAt")) or utc_now()
            elapsed_ms = 0
            if self.answer_opened_at:
                elapsed_ms = max(0, int((received - self.answer_opened_at).total_seconds() * 1000))

            record = AnswerRecord(uid, nickname, message, parsed, seq, received.isoformat(), elapsed_ms, correct)
            self.answers[uid] = record
            self.participants[uid].nickname = nickname
            self._rebuild_correct_order()

            if q.auto_close_quota and q.scoring_mode in {"first_n", "mixed"} and len(self.correct_order) >= q.first_n:
                self.close_answers(auto=True)

    def _parse_answer(self, q: Question, message: str) -> Optional[str]:
        text = unicodedata.normalize("NFKC", message.strip())
        if q.kind == "multiple":
            match = re.fullmatch(r"!(\d{1,2})", text)
            if not match:
                return None
            value = int(match.group(1))
            if value < 1 or value > len(q.choices):
                return None
            return str(value)
        if q.kind == "ox":
            match = re.fullmatch(r"!([oOxXㅇㄴ])", text)
            if not match:
                return None
            return "O" if match.group(1).casefold() in {"o", "ㅇ"} else "X"
        if q.kind == "short":
            match = re.fullmatch(r"!정답\s+(.+)", text)
            return match.group(1).strip() if match else None
        if q.kind == "number":
            match = re.fullmatch(r"!(?:숫자\s+)?([-+]?\d+(?:\.\d+)?)", text)
            return match.group(1) if match else None
        return None

    @staticmethod
    def _normalize_short(text: str, *, ignore_space: bool, ignore_punct: bool, ignore_case: bool) -> str:
        value = unicodedata.normalize("NFKC", text.strip())
        if ignore_case:
            value = value.casefold()
        if ignore_space:
            value = re.sub(r"\s+", "", value)
        if ignore_punct:
            punctuation = string.punctuation + "·ㆍ…‘’“”「」『』【】（）()[]{}<>"
            value = value.translate(str.maketrans("", "", punctuation))
        return value

    def _is_correct(self, q: Question, parsed: str) -> bool:
        if q.kind in {"multiple", "ox"}:
            return parsed.strip().casefold() == str(q.answer).strip().casefold()
        if q.kind == "number":
            try:
                return abs(float(parsed) - float(q.answer)) <= max(0.0, float(q.number_tolerance))
            except Exception:
                return False
        target = self._normalize_short(parsed, ignore_space=q.ignore_space, ignore_punct=q.ignore_punct, ignore_case=q.ignore_case)
        accepted = [q.answer, *q.accepted_answers]
        return any(
            target == self._normalize_short(str(answer), ignore_space=q.ignore_space, ignore_punct=q.ignore_punct, ignore_case=q.ignore_case)
            for answer in accepted
            if str(answer).strip()
        )

    def _rebuild_correct_order(self) -> None:
        correct = sorted((a for a in self.answers.values() if a.correct), key=lambda a: a.seq)
        self.correct_order = []
        for rank, record in enumerate(correct, start=1):
            record.rank = rank
            self.correct_order.append(record.user_id)

    def _finalize_scores(self) -> None:
        if self._last_finalized_index == self.current_index:
            return
        q = self.current_question
        if not q:
            return
        correct_records = sorted((a for a in self.answers.values() if a.correct), key=lambda a: a.seq)
        correct_ids = {a.user_id for a in correct_records}
        for i, record in enumerate(correct_records):
            participant = self.participants.get(record.user_id)
            if not participant:
                continue
            participant.correct_count += 1
            participant.streak += 1
            participant.best_streak = max(participant.best_streak, participant.streak)
            participant.total_correct_elapsed_ms += max(0, record.elapsed_ms)
            participant.correct_elapsed_samples += 1
            if q.scoring_mode == "all":
                participant.score += q.base_points
            elif q.scoring_mode == "first_n":
                if i < q.first_n:
                    participant.score += q.rank_points[i] if i < len(q.rank_points) else q.base_points
            else:
                participant.score += q.base_points
                if i < q.first_n:
                    participant.score += q.rank_points[i] if i < len(q.rank_points) else 0
        for uid, participant in self.participants.items():
            if uid not in correct_ids:
                participant.streak = 0
        self._last_finalized_index = self.current_index

    def remaining_ms(self) -> Optional[int]:
        with self.lock:
            if self.state != "ANSWERING" or self.timer_deadline_monotonic is None:
                return None
            return max(0, int((self.timer_deadline_monotonic - time.monotonic()) * 1000))

    def ranking(self, limit: int = 10) -> list[dict[str, Any]]:
        with self.lock:
            rows = list(self.participants.values())
            if self.ranking_mode == "score":
                rows.sort(key=lambda p: (-p.score, -p.correct_count, p.total_correct_elapsed_ms, p.joined_at, p.user_id))
            elif self.ranking_mode == "streak":
                rows.sort(key=lambda p: (-p.best_streak, -p.correct_count, -p.score, p.joined_at, p.user_id))
            else:
                rows.sort(key=lambda p: (-p.correct_count, p.total_correct_elapsed_ms, -p.score, p.joined_at, p.user_id))
            output: list[dict[str, Any]] = []
            for rank, participant in enumerate(rows[: max(1, limit)], start=1):
                avg_ms = int(participant.total_correct_elapsed_ms / participant.correct_elapsed_samples) if participant.correct_elapsed_samples else None
                output.append({
                    "rank": rank,
                    "display": participant.display,
                    "correct": participant.correct_count,
                    "score": participant.score,
                    "streak": participant.best_streak,
                    "avgMs": avg_ms,
                })
            return output

    def answer_command_hint(self, q: Optional[Question] = None) -> str:
        q = q or self.current_question
        if not q:
            return ""
        if q.kind == "multiple":
            return "   ".join(f"!{i + 1}" for i in range(len(q.choices)))
        if q.kind == "ox":
            return "!O   !X"
        if q.kind == "short":
            return "!정답 [답변]"
        if q.kind == "number":
            return "!숫자 [숫자]"
        return ""

    def public_state(self) -> dict[str, Any]:
        with self.lock:
            q = self.current_question
            answers = list(self.answers.values())
            correct = sorted((a for a in answers if a.correct), key=lambda a: a.seq)
            first_correct = [
                {
                    "rank": i + 1,
                    "display": f"{record.nickname}({record.user_id})",
                    "elapsedMs": record.elapsed_ms,
                }
                for i, record in enumerate(correct[:10])
            ]
            return {
                "app": {"name": APP_NAME, "version": APP_VERSION},
                "state": self.state,
                "connected": self.connected,
                "streamerId": self.streamer_id,
                "participants": len(self.participants),
                "answered": len(answers),
                "correct": len(correct),
                "questionIndex": self.current_index,
                "questionCount": len(self.questions),
                "question": asdict(q) if q else None,
                "remainingMs": self.remaining_ms(),
                "notice": self.overlay_notice,
                "integrityWarning": self.integrity_warning,
                "firstCorrect": first_correct,
                "rankingMode": self.ranking_mode,
                "ranking": self.ranking(10),
                "visual": dict(self.visual),
                "answerHint": self.answer_command_hint(q),
                "answerGateSeq": self.answer_gate_seq,
                "lastSeq": self.last_seq,
            }
