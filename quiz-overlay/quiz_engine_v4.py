from __future__ import annotations

import threading
from collections import deque
from typing import Any

from quiz_engine_v3 import QuizEngineV3
from common import parse_iso, utc_now


class QuizEngineV4(QuizEngineV3):
    """v0.4 engine: keep participant chat tracking separate from answer scoring.

    Only registered participants are retained. Non-participant chat is never
    added to the participant chat feed. The feed is memory-only and bounded.
    """

    def __init__(self) -> None:
        super().__init__()
        self._participant_chat = deque(maxlen=500)
        self.participant_chat_total = 0
        self.chat_version = 1
        self._chat_condition = threading.Condition(self.lock)

    def _touch_chat(self) -> None:
        self.chat_version += 1
        self._chat_condition.notify_all()

    def wait_for_chat_update(self, last_version: int, timeout: float = 10.0) -> int:
        with self._chat_condition:
            if self.chat_version <= last_version:
                self._chat_condition.wait(timeout=max(0.05, timeout))
            return self.chat_version

    def start_recruitment(self) -> bool:
        with self.lock:
            self._participant_chat.clear()
            self.participant_chat_total = 0
            self._touch_chat()
        return super().start_recruitment()

    def reset_session(self) -> None:
        with self.lock:
            self._participant_chat.clear()
            self.participant_chat_total = 0
            self._touch_chat()
        super().reset_session()

    def clear_participant_chat(self) -> None:
        with self.lock:
            self._participant_chat.clear()
            self._touch_chat()

    def participant_chat_feed(self, limit: int = 200) -> list[dict[str, Any]]:
        with self.lock:
            rows = list(self._participant_chat)
            if limit > 0:
                rows = rows[-limit:]
            return list(reversed(rows))

    def latest_participant_chat(self) -> dict[str, Any] | None:
        with self.lock:
            return dict(self._participant_chat[-1]) if self._participant_chat else None

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
            # Replay/duplicate messages must not be duplicated in the chat feed.
            if seq in self._seen_seqs:
                return
            was_participant = uid in self.participants
            state_before = self.state
            question_before = self.current_index

        # v3 continues to own recruitment, answer validation, scoring and seq gates.
        super().process_chat(seq, event)

        with self.lock:
            is_participant = uid in self.participants
            # Track from the join command onward. A cancellation command is still
            # shown if the user was a participant immediately before it.
            if not (was_participant or is_participant):
                return

            answer = self.answers.get(uid)
            accepted_answer = bool(answer and answer.seq == seq)
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
                "cancelled": message == "!취소" and was_participant and not is_participant,
                "joined": message == "!참여" and (not was_participant and is_participant),
            }
            self._participant_chat.append(row)
            self.participant_chat_total += 1
            self._touch_chat()
