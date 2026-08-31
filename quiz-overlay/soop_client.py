from __future__ import annotations

import json
import threading
import time
from typing import Callable, Optional

import websocket

from quiz_engine import QuizEngine


class SoopChatClient:
    """Thin downstream client for Unified Core protocol v4."""

    def __init__(self, engine: QuizEngine, status_callback: Optional[Callable[[str], None]] = None) -> None:
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
        if self.thread and self.thread.is_alive():
            self.disconnect()
        self.url = url
        self.streamer_id = streamer_id
        self.stop_flag.clear()
        self.subscribed = False
        self._resume_from = self.last_event_seq
        self.thread = threading.Thread(target=self._run, daemon=True, name="soop-chat-client")
        self.thread.start()
        self._status("방송 채팅 연결 중")

    def disconnect(self) -> None:
        self.stop_flag.set()
        ws = self.ws
        self.ws = None
        if ws:
            try:
                ws.close()
            except Exception:
                pass
        if self.thread and self.thread.is_alive() and self.thread is not threading.current_thread():
            self.thread.join(timeout=1.2)
        self.thread = None
        self.subscribed = False
        self.engine.set_disconnected("사용자 연결 해제")
        self._status("연결 안 됨")

    def _run(self) -> None:
        backoff = 0.8
        while not self.stop_flag.is_set():
            try:
                self.ws = websocket.WebSocketApp(
                    self.url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self.ws.run_forever(ping_interval=20, ping_timeout=10, skip_utf8_validation=True)
            except Exception as exc:
                self._status(f"연결 오류 · {exc}")
            if self.stop_flag.is_set():
                break
            self.engine.set_disconnected("실시간 연결 재시도")
            self._status("연결 복구 중")
            time.sleep(backoff)
            backoff = min(8.0, backoff * 1.7)

    def _send(self, payload: dict) -> None:
        ws = self.ws
        if not ws:
            return
        try:
            ws.send(json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass

    def _on_open(self, ws) -> None:
        self._status("내부 엔진 연결됨 · 방송 확인 중")

    def _on_message(self, ws, text: str) -> None:
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
            self._send({
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
                self._send({"action": "resume", "fromSeq": self._resume_from})
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

    def _on_error(self, ws, error) -> None:
        if not self.stop_flag.is_set():
            self._status(f"방송 채팅 오류 · {error}")

    def _on_close(self, ws, code, reason) -> None:
        self.subscribed = False
        if not self.stop_flag.is_set():
            self._resume_from = self.last_event_seq
            self._status("연결 복구 중")
