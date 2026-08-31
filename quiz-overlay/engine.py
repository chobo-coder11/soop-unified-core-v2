from __future__ import annotations

import json
import queue
import re
import threading
import time
import unicodedata
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

try:
    import websocket  # websocket-client
except Exception:
    websocket = None

from common import (APP_NAME, APP_VERSION, Question, Participant, AnswerRecord, utc_now, parse_iso, norm_short, safe_int)

class QuizEngine:
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
        self.answer_open_server_time: Optional[datetime] = None
        self.clock_offset_sec = 0.0
        self.integrity_warning = ""
        self.last_gap: Optional[dict[str, Any]] = None
        self.ranking_mode = "correct_count"
        self.overlay_notice = ""
        self.timer_deadline_monotonic: Optional[float] = None
        self.timer_thread: Optional[threading.Thread] = None
        self.event_log: list[str] = []
        self._seen_seqs: set[int] = set()
        self._last_finalized_index = -1

    def log(self, text: str) -> None:
        with self.lock:
            stamp = datetime.now().strftime("%H:%M:%S")
            self.event_log.append(f"[{stamp}] {text}")
            self.event_log = self.event_log[-200:]

    @property
    def current_question(self) -> Optional[Question]:
        if not self.questions:
            return None
        if self.current_index < 0 or self.current_index >= len(self.questions):
            return None
        return self.questions[self.current_index]

    def set_connected(self, streamer_id: str) -> None:
        with self.lock:
            self.connected = True
            self.streamer_id = streamer_id
            if self.state == "DISCONNECTED":
                self.state = "READY"
            self.log(f"SOOP 연결됨: {streamer_id}")

    def set_disconnected(self, reason: str = "") -> None:
        with self.lock:
            self.connected = False
            if self.state == "ANSWERING":
                self.state = "QUESTION_CLOSED"
                self.timer_deadline_monotonic = None
                self.integrity_warning = "답변 접수 중 소켓 연결이 끊겨 문제를 안전하게 마감했습니다. 재진행을 권장합니다."
                self.overlay_notice = "연결 문제로 답변 접수가 중단되었습니다"
            elif self.state in {"READY", "RECRUITING"}:
                self.state = "DISCONNECTED"
            if reason:
                self.log(f"연결 종료: {reason}")

    def start_recruitment(self) -> bool:
        with self.lock:
            if self.state not in {"READY", "LOCKED", "FINISHED"}:
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
            self.log(f"참가 모집 마감 ({len(self.participants)}명)")
            return True

    def show_question(self) -> bool:
        with self.lock:
            q = self.current_question
            if not q or self.state not in {"LOCKED", "ANSWER_REVEALED", "QUESTION_CLOSED"}:
                return False
            self.answers.clear()
            self.correct_order.clear()
            self.timer_deadline_monotonic = None
            self.answer_open_server_time = None
            self.state = "QUESTION_SHOWN"
            self.overlay_notice = "문제를 확인해주세요 · 아직 정답은 받지 않습니다"
            self.log(f"Q{self.current_index+1} 문제 공개")
            return True

    def open_answers(self) -> bool:
        with self.lock:
            q = self.current_question
            if not q or self.state != "QUESTION_SHOWN":
                return False
            self.answer_gate_seq = self.last_seq
            self.answer_open_server_time = utc_now() + timedelta(seconds=self.clock_offset_sec)
            self.state = "ANSWERING"
            self.timer_deadline_monotonic = time.monotonic() + q.duration_sec
            self.overlay_notice = "START! 정답을 입력해주세요"
            self.log(f"Q{self.current_index+1} 답변 시작 · gate seq={self.answer_gate_seq}")
            if q.auto_close_time:
                self._start_timer(q.duration_sec)
            return True

    def _start_timer(self, sec: int) -> None:
        def run() -> None:
            deadline = time.monotonic() + sec
            while time.monotonic() < deadline:
                time.sleep(0.1)
                with self.lock:
                    if self.state != "ANSWERING":
                        return
            self.close_answers(auto=True)
        t = threading.Thread(target=run, daemon=True)
        self.timer_thread = t
        t.start()

    def close_answers(self, auto: bool = False) -> bool:
        with self.lock:
            if self.state != "ANSWERING":
                return False
            self.state = "QUESTION_CLOSED"
            self.timer_deadline_monotonic = None
            self.overlay_notice = "정답 입력이 마감되었습니다"
            self.log(f"답변 마감{'(자동)' if auto else ''} · {len(self.answers)}명")
            return True

    def reveal_answer(self) -> bool:
        with self.lock:
            if self.state != "QUESTION_CLOSED":
                return False
            self._finalize_scores()
            self.state = "ANSWER_REVEALED"
            self.overlay_notice = "정답 공개"
            self.log(f"Q{self.current_index+1} 정답 공개")
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
            self.overlay_notice = f"다음 문제 준비 · Q{self.current_index+1}"
            self.log(f"Q{self.current_index+1} 준비")
            return True

    def _finalize_scores(self) -> None:
        if self._last_finalized_index == self.current_index:
            return
        q = self.current_question
        if not q:
            return
        correct_records = sorted((a for a in self.answers.values() if a.correct), key=lambda x: x.seq)
        for i, rec in enumerate(correct_records):
            p = self.participants.get(rec.user_id)
            if not p:
                continue
            p.correct_count += 1
            p.streak += 1
            p.best_streak = max(p.best_streak, p.streak)
            p.total_correct_elapsed_ms += max(0, rec.elapsed_ms)
            p.correct_elapsed_samples += 1
            if q.scoring_mode == "all":
                p.score += q.base_points
            elif q.scoring_mode == "first_n":
                if i < q.first_n:
                    p.score += q.rank_points[i] if i < len(q.rank_points) else q.base_points
            else:  # mixed
                p.score += q.base_points
                if i < q.first_n:
                    p.score += q.rank_points[i] if i < len(q.rank_points) else 0
        wrong_ids = set(self.answers) - {r.user_id for r in correct_records}
        for uid in wrong_ids:
            p = self.participants.get(uid)
            if p:
                p.streak = 0
        self._last_finalized_index = self.current_index

    def process_chat(self, seq: int, event: dict[str, Any]) -> None:
        with self.lock:
            if seq <= 0 or seq in self._seen_seqs:
                return
            self._seen_seqs.add(seq)
            if len(self._seen_seqs) > 10000:
                floor = max(0, self.last_seq - 5000)
                self._seen_seqs = {s for s in self._seen_seqs if s >= floor}
            self.last_seq = max(self.last_seq, seq)
            user = event.get("user") or {}
            uid = str(user.get("id") or "").strip()
            nick = str(user.get("nickname") or uid or "익명").strip()
            msg = str(event.get("message") or "").strip()
            if not uid or not msg:
                return

            if self.state == "RECRUITING":
                if msg == "!참여":
                    if uid not in self.participants:
                        self.participants[uid] = Participant(uid, nick, utc_now().isoformat())
                        self.log(f"참가: {nick}({uid})")
                    else:
                        self.participants[uid].nickname = nick
                    return
                if msg == "!취소" and uid in self.participants:
                    del self.participants[uid]
                    self.log(f"참가 취소: {nick}({uid})")
                return

            if self.state != "ANSWERING" or uid not in self.participants:
                return
            if seq <= self.answer_gate_seq:
                return
            q = self.current_question
            if not q:
                return
            parsed = self._parse_answer(q, msg)
            if parsed is None:
                return
            prev = self.answers.get(uid)
            if prev and q.answer_policy == "first":
                return
            correct = self._is_correct(q, parsed)
            received = parse_iso(event.get("receivedAt")) or utc_now()
            if self.answer_open_server_time:
                elapsed_ms = max(0, int((received - self.answer_open_server_time).total_seconds() * 1000))
            else:
                elapsed_ms = 0
            rec = AnswerRecord(uid, nick, msg, parsed, seq, received.isoformat(), elapsed_ms, correct)
            self.answers[uid] = rec
            self.participants[uid].nickname = nick
            self._rebuild_correct_order(q)

            if q.auto_close_quota and q.scoring_mode in {"first_n", "mixed"}:
                if len(self.correct_order) >= q.first_n:
                    self.close_answers(auto=True)

    def _rebuild_correct_order(self, q: Question) -> None:
        correct = sorted((a for a in self.answers.values() if a.correct), key=lambda x: x.seq)
        self.correct_order = []
        for idx, rec in enumerate(correct, start=1):
            rec.rank = idx
            self.correct_order.append(rec.user_id)

    def _parse_answer(self, q: Question, msg: str) -> Optional[str]:
        text = unicodedata.normalize("NFKC", msg.strip())
        if q.kind == "multiple":
            m = re.fullmatch(r"!(\d{1,2})", text)
            if not m:
                return None
            n = int(m.group(1))
            if n < 1 or n > max(2, len(q.choices)):
                return None
            return str(n)
        if q.kind == "ox":
            m = re.fullmatch(r"!([oOxXㅇㄴ])", text)
            if not m:
                return None
            v = m.group(1).casefold()
            return "O" if v in {"o", "ㅇ"} else "X"
        if q.kind == "short":
            m = re.fullmatch(r"!정답\s+(.+)", text)
            if not m:
                return None
            return m.group(1).strip()
        if q.kind == "number":
            m = re.fullmatch(r"!(?:숫자\s+)?([-+]?\d+(?:\.\d+)?)", text)
            if not m:
                return None
            return m.group(1)
        return None

    def _is_correct(self, q: Question, parsed: str) -> bool:
        if q.kind in {"multiple", "ox"}:
            return parsed.strip().casefold() == str(q.answer).strip().casefold()
        if q.kind == "number":
            try:
                return abs(float(parsed) - float(q.answer)) <= q.number_tolerance
            except Exception:
                return False
        answers = [q.answer] + list(q.accepted_answers)
        target = norm_short(parsed, ignore_space=q.ignore_space, ignore_punct=q.ignore_punct, ignore_case=q.ignore_case)
        return any(target == norm_short(a, ignore_space=q.ignore_space, ignore_punct=q.ignore_punct, ignore_case=q.ignore_case) for a in answers if str(a).strip())

    def ranking(self, limit: int = 10) -> list[dict[str, Any]]:
        with self.lock:
            rows = list(self.participants.values())
            if self.ranking_mode == "score":
                rows.sort(key=lambda p: (-p.score, -p.correct_count, p.total_correct_elapsed_ms, p.joined_at, p.user_id))
            elif self.ranking_mode == "streak":
                rows.sort(key=lambda p: (-p.best_streak, -p.correct_count, -p.score, p.joined_at, p.user_id))
            else:
                rows.sort(key=lambda p: (-p.correct_count, p.total_correct_elapsed_ms, -p.score, p.joined_at, p.user_id))
            out = []
            for idx, p in enumerate(rows[:limit], start=1):
                avg = int(p.total_correct_elapsed_ms / p.correct_elapsed_samples) if p.correct_elapsed_samples else None
                out.append({
                    "rank": idx,
                    "display": p.display,
                    "correct": p.correct_count,
                    "score": p.score,
                    "streak": p.best_streak,
                    "avgMs": avg,
                })
            return out

    def remaining_ms(self) -> Optional[int]:
        with self.lock:
            if self.state != "ANSWERING" or self.timer_deadline_monotonic is None:
                return None
            return max(0, int((self.timer_deadline_monotonic - time.monotonic()) * 1000))

    def public_state(self) -> dict[str, Any]:
        with self.lock:
            q = self.current_question
            answers = list(self.answers.values())
            correct = sorted((a for a in answers if a.correct), key=lambda a: a.seq)
            first_correct = [
                {"rank": i + 1, "display": f"{a.nickname}({a.user_id})", "elapsedMs": a.elapsed_ms}
                for i, a in enumerate(correct[:10])
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
            }


class CoreSocketClient:
    def __init__(self, engine: QuizEngine, event_queue: queue.Queue[str]) -> None:
        self.engine = engine
        self.event_queue = event_queue
        self.url = "ws://127.0.0.1:8080/v1/ws"
        self.streamer_id = ""
        self.ws: Any = None
        self.thread: Optional[threading.Thread] = None
        self.stop_flag = threading.Event()
        self._ping_sent_at: Optional[float] = None

    def connect(self, url: str, streamer_id: str) -> None:
        if websocket is None:
            raise RuntimeError("websocket-client 패키지가 필요합니다.")
        self.disconnect()
        self.url = url.strip()
        self.streamer_id = streamer_id.strip()
        self.stop_flag.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        backoff = 1.0
        while not self.stop_flag.is_set():
            try:
                self.ws = websocket.WebSocketApp(
                    self.url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self.ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as e:
                self._emit(f"소켓 오류: {e}")
            if self.stop_flag.is_set():
                break
            self._emit(f"재연결 시도 ({backoff:.0f}초 후)")
            time.sleep(backoff)
            backoff = min(10.0, backoff * 1.7)

    def _on_open(self, ws: Any) -> None:
        self._emit("Unified Core 소켓 연결 성공")

    def _on_message(self, ws: Any, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except Exception:
            return
        typ = msg.get("type")
        if typ == "hello":
            ws.send(json.dumps({"action": "subscribe", "streamers": [self.streamer_id], "events": ["CHAT_MESSAGE"]}, ensure_ascii=False))
            if self.engine.last_seq > 0:
                ws.send(json.dumps({"action": "resume", "fromSeq": self.engine.last_seq}))
            self._ping_sent_at = time.time()
            ws.send(json.dumps({"action": "ping"}))
            return
        if typ == "subscribed":
            self.engine.set_connected(self.streamer_id)
            self._emit(f"채팅 구독 시작: {self.streamer_id}")
            return
        if typ == "pong":
            server_at = parse_iso(msg.get("at"))
            if server_at and self._ping_sent_at:
                recv = time.time()
                midpoint = (self._ping_sent_at + recv) / 2.0
                local_mid = datetime.fromtimestamp(midpoint, timezone.utc)
                self.engine.clock_offset_sec = (server_at - local_mid).total_seconds()
            return
        if typ == "gap":
            self.engine.integrity_warning = f"이벤트 누락 감지: seq {msg.get('fromSeq')}~{msg.get('toSeq')} · 선착순 결과 확인 필요"
            self.engine.last_gap = msg
            self._emit(self.engine.integrity_warning)
            return
        if typ == "resume_unavailable":
            self.engine.integrity_warning = "재연결 구간을 복구할 수 없어 선착순 정확도 확인이 필요합니다."
            self._emit(self.engine.integrity_warning)
            return
        if typ == "event":
            seq = safe_int(msg.get("seq"), 0)
            event = msg.get("event") or {}
            if event.get("category") == "chat" or event.get("type") == "CHAT_MESSAGE":
                self.engine.process_chat(seq, event)

    def _on_error(self, ws: Any, err: Any) -> None:
        self._emit(f"소켓 오류: {err}")

    def _on_close(self, ws: Any, code: Any, reason: Any) -> None:
        if not self.stop_flag.is_set():
            self.engine.set_disconnected(str(reason or code or "연결 종료"))

    def _emit(self, text: str) -> None:
        self.engine.log(text)
        try:
            self.event_queue.put_nowait(text)
        except Exception:
            pass

    def disconnect(self) -> None:
        self.stop_flag.set()
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass
        self.ws = None
        self.engine.set_disconnected("사용자 연결 해제")
