from __future__ import annotations

import json
import threading
import time
from typing import Callable, Optional, Any

from quiz_engine_v4 import QuizEngineV4
from soop_client_v3 import SoopChatClientV3


class SoopChatClientV4(SoopChatClientV3):
    """v0.4 downstream client with user-visible WebSocket diagnostics."""

    def __init__(self, engine: QuizEngineV4, status_callback: Optional[Callable[[str], None]] = None) -> None:
        super().__init__(engine, status_callback)
        self.hello_protocol: int | None = None
        self.hello_count = 0
        self.subscribe_count = 0
        self.event_count = 0
        self.reconnect_count = 0
        self.gap_count = 0
        self.resume_unavailable_count = 0
        self.last_frame_monotonic = 0.0
        self.last_event_monotonic = 0.0
        self.last_event_epoch = 0.0
        self.last_error = ""
        self.last_close_code: Any = None
        self.last_close_reason = ""
        self._diag_lock = threading.RLock()

    def connect(self, url: str, streamer_id: str) -> None:
        with self._diag_lock:
            self.last_error = ""
            self.last_close_code = None
            self.last_close_reason = ""
        super().connect(url, streamer_id)

    def _on_open(self, generation: int, ws) -> None:
        with self._diag_lock:
            self.last_frame_monotonic = time.monotonic()
        super()._on_open(generation, ws)

    def _on_message(self, generation: int, ws, text: str) -> None:
        if generation != self._generation:
            return
        now = time.monotonic()
        with self._diag_lock:
            self.last_frame_monotonic = now
        try:
            message = json.loads(text)
        except Exception:
            super()._on_message(generation, ws, text)
            return

        kind = str(message.get("type") or "")
        with self._diag_lock:
            if kind == "hello":
                self.hello_count += 1
                try:
                    self.hello_protocol = int(message.get("protocol") or 0)
                except Exception:
                    self.hello_protocol = None
            elif kind == "subscribed":
                self.subscribe_count += 1
            elif kind == "event":
                self.event_count += 1
                self.last_event_monotonic = now
                self.last_event_epoch = time.time()
            elif kind == "gap":
                self.gap_count += 1
            elif kind == "resume_unavailable":
                self.resume_unavailable_count += 1
        super()._on_message(generation, ws, text)

    def _on_error(self, generation: int, ws, error) -> None:
        with self._diag_lock:
            self.last_error = str(error)
        super()._on_error(generation, ws, error)

    def _on_close(self, generation: int, ws, code, reason) -> None:
        with self._diag_lock:
            self.last_close_code = code
            self.last_close_reason = str(reason or "")
            if generation == self._generation and not self.stop_flag.is_set():
                self.reconnect_count += 1
        super()._on_close(generation, ws, code, reason)

    def diagnostics(self) -> dict[str, Any]:
        with self._diag_lock:
            now = time.monotonic()
            event_age = None
            if self.last_event_monotonic > 0:
                event_age = max(0.0, now - self.last_event_monotonic)
            thread_alive = bool(self.thread and self.thread.is_alive())
            if self.subscribed and thread_alive:
                health = "정상"
            elif thread_alive and self.status in {"방송 채팅 연결 중", "내부 엔진 연결됨 · 방송 확인 중", "연결 복구 중"}:
                health = "연결 중"
            elif thread_alive:
                health = "확인 필요"
            else:
                health = "연결 안 됨"
            return {
                "health": health,
                "status": self.status,
                "subscribed": self.subscribed,
                "threadAlive": thread_alive,
                "protocol": self.hello_protocol,
                "helloCount": self.hello_count,
                "subscribeCount": self.subscribe_count,
                "eventCount": self.event_count,
                "currentSeq": self.current_seq,
                "lastEventSeq": self.last_event_seq,
                "lastEventAgeSec": event_age,
                "reconnectCount": self.reconnect_count,
                "gapCount": self.gap_count,
                "resumeUnavailableCount": self.resume_unavailable_count,
                "lastError": self.last_error,
                "lastCloseCode": self.last_close_code,
                "lastCloseReason": self.last_close_reason,
            }
