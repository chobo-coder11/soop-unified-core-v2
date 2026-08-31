from __future__ import annotations

import json
import threading
import time
from typing import Callable, Optional

import websocket

from quiz_engine_v3 import QuizEngineV3


class SoopChatClientV3:
    """Unified Core v4 downstream client tuned for desktop UI responsiveness."""

    def __init__(self, engine: QuizEngineV3, status_callback: Optional[Callable[[str], None]] = None) -> None:
        self.engine = engine
        self.status_callback = status_callback
        self.ws: Optional[websocket.WebSocketApp] = None
        self.thread: Optional[threading.Thread] = None
        self.stop_flag = threading.Event()
        self.url = ""
        self.streamer_id = ""
        self.current_seq = 0
        self.last_event_seq = 0
        self.subscribed = False
        self.status = "연결 안 됨"
        self._resume_from = 0
        self._generation = 0
        self._lock = threading.RLock()

    def _status(self, text: str) -> None:
        self.status = text
        if self.status_callback:
            try:
                self.status_callback(text)
            except Exception:
                pass

    def connect(self, url: str, streamer_id: str) -> None:
        streamer_id = streamer_id.strip()
        if not streamer_id:
            raise ValueError("스트리머 ID를 입력해주세요.")
        with self._lock:
            self._generation += 1
            generation = self._generation
            old_ws = self.ws
            self.stop_flag.set()
            if old_ws:
                threading.Thread(target=self._safe_close, args=(old_ws,), daemon=True).start()
            self.stop_flag = threading.Event()
            self.url = url
            self.streamer_id = streamer_id
            self.subscribed = False
            self._resume_from = self.last_event_seq
            self.thread = threading.Thread(target=self._run, args=(generation, self.stop_flag), daemon=True, name=f"soop-chat-{generation}")
            self.thread.start()
        self._status("방송 채팅 연결 중")

    @staticmethod
    def _safe_close(ws) -> None:
        try:
            ws.close()
        except Exception:
            pass

    def disconnect(self, *, wait: bool = False) -> None:
        with self._lock:
            self._generation += 1
            stop = self.stop_flag
            stop.set()
            ws = self.ws
            self.ws = None
            thread = self.thread
            self.thread = None
            self.subscribed = False
        if ws:
            closer = threading.Thread(target=self._safe_close, args=(ws,), daemon=True, name="soop-close")
            closer.start()
            if wait:
                closer.join(timeout=0.4)
        if wait and thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=0.6)
        self.engine.set_disconnected("사용자 연결 해제")
        self._status("연결 안 됨")

    def _run(self, generation: int, stop: threading.Event) -> None:
        backoff = 0.7
        while not stop.is_set():
            try:
                app = websocket.WebSocketApp(
                    self.url,
                    on_open=lambda ws: self._on_open(generation, ws),
                    on_message=lambda ws, text: self._on_message(generation, ws, text),
                    on_error=lambda ws, err: self._on_error(generation, ws, err),
                    on_close=lambda ws, code, reason: self._on_close(generation, ws, code, reason),
                )
                with self._lock:
                    if generation != self._generation:
                        return
                    self.ws = app
                app.run_forever(ping_interval=20, ping_timeout=10, skip_utf8_validation=True)
            except Exception as exc:
                if generation == self._generation:
                    self._status(f"연결 오류 · {exc}")
            if stop.is_set() or generation != self._generation:
                break
            self.engine.set_disconnected("실시간 연결 재시도")
            self._status("연결 복구 중")
            stop.wait(backoff)
            backoff = min(7.0, backoff * 1.6)

    def _send(self, generation: int, payload: dict) -> None:
        with self._lock:
            if generation != self._generation:
                return
            ws = self.ws
        if not ws:
            return
        try:
            ws.send(json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass

    def _on_open(self, generation: int, ws) -> None:
        if generation != self._generation:
            return
        self._status("내부 엔진 연결됨 · 방송 확인 중")

    def _on_message(self, generation: int, ws, text: str) -> None:
        if generation != self._generation:
            return
        try:
            message = json.loads(text)
        except Exception:
            return
        kind = str(message.get("type") or "")
        current = message.get("currentSeq")
        if isinstance(current, int):
            self.current_seq = max(self.current_seq, current)

        if kind == "hello":
            if int(message.get("protocol") or 0) != 4:
                self._status("지원하지 않는 내부 프로토콜")
                return
            self._send(generation, {
                "action": "subscribe",
                "streamers": [self.streamer_id],
                "events": ["CHAT_MESSAGE"],
            })
            return

        if kind == "subscribed":
            self.subscribed = True
            self.engine.set_connected(self.streamer_id)
            self._status("방송 채팅 연결됨")
            if self._resume_from > 0:
                self._send(generation, {"action": "resume", "fromSeq": self._resume_from})
                self._resume_from = 0
            return

        if kind == "event":
            seq = int(message.get("seq") or 0)
            event = message.get("event") or {}
            if seq <= 0 or not isinstance(event, dict):
                return
            self.current_seq = max(self.current_seq, seq)
            self.last_event_seq = max(self.last_event_seq, seq)
            self.engine.process_chat(seq, event)
            return

        if kind == "gap":
            self.engine.on_gap(message)
            return

        if kind == "resume_unavailable":
            self.engine.on_gap({
                "fromSeq": message.get("fromSeq"),
                "toSeq": message.get("currentSeq"),
                "reason": "resume_unavailable",
            })
            return

        if kind == "error":
            self._status(f"내부 연결 오류 · {message.get('error', 'unknown')}")

    def _on_error(self, generation: int, ws, error) -> None:
        if generation == self._generation and not self.stop_flag.is_set():
            self._status(f"방송 채팅 오류 · {error}")

    def _on_close(self, generation: int, ws, code, reason) -> None:
        if generation != self._generation:
            return
        self.subscribed = False
        if not self.stop_flag.is_set():
            self._resume_from = self.last_event_seq
            self._status("연결 복구 중")
