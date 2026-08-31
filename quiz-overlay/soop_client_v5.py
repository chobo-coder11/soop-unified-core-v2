from __future__ import annotations

import json
import queue
import threading
import time
from typing import Any, Callable, Optional

from quiz_engine_v5 import QuizEngineV5
from soop_client_v4 import SoopChatClientV4


class SoopChatClientV5(SoopChatClientV4):
    """v0.5 WebSocket client.

    The socket callback never performs quiz scoring. It only parses the small
    downstream envelope and enqueues canonical events. A dedicated worker
    preserves event order and keeps answer collection alive even if the GUI is
    busy painting or a browser overlay reconnects.
    """

    def __init__(self, engine: QuizEngineV5, status_callback: Optional[Callable[[str], None]] = None) -> None:
        super().__init__(engine, status_callback)
        self.engine = engine
        self._event_queue: queue.Queue[tuple[int, int, dict[str, Any]]] = queue.Queue(maxsize=20000)
        self._worker_stop = threading.Event()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True, name="quiz-event-worker-v5")
        self._worker.start()
        self.processed_event_count = 0
        self.queue_drop_count = 0
        self.queue_peak = 0
        self.ping_count = 0
        self.pong_count = 0
        self.last_pong_monotonic = 0.0
        self.last_resumed_replayed = 0
        self._overflow_warned_at = 0.0
        self._heartbeat_stop = threading.Event()
        self._heartbeat = threading.Thread(target=self._heartbeat_loop, daemon=True, name="quiz-heartbeat-v5")
        self._heartbeat.start()

    def _worker_loop(self) -> None:
        while not self._worker_stop.is_set():
            try:
                generation, seq, event = self._event_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                if generation == self._generation:
                    self.engine.process_chat(seq, event)
                    with self._diag_lock:
                        self.processed_event_count += 1
            except Exception as exc:
                with self._diag_lock:
                    self.last_error = f"이벤트 처리 오류: {exc}"
                # Scoring exceptions are integrity relevant while a question is live.
                if self.engine.state == "ANSWERING":
                    self.engine.on_gap({"fromSeq": seq, "toSeq": seq, "reason": "local_processing_error"})
            finally:
                self._event_queue.task_done()

    def _heartbeat_loop(self) -> None:
        while not self._heartbeat_stop.wait(12.0):
            try:
                with self._lock:
                    generation = self._generation
                    active = bool(self.subscribed and self.ws and not self.stop_flag.is_set())
                if not active:
                    continue
                with self._diag_lock:
                    self.ping_count += 1
                self._send(generation, {"action": "ping"})
            except Exception:
                pass

    def _enqueue_event(self, generation: int, seq: int, event: dict[str, Any]) -> None:
        try:
            self._event_queue.put_nowait((generation, seq, event))
            with self._diag_lock:
                self.queue_peak = max(self.queue_peak, self._event_queue.qsize())
        except queue.Full:
            with self._diag_lock:
                self.queue_drop_count += 1
            now = time.monotonic()
            if now - self._overflow_warned_at > 2.0:
                self._overflow_warned_at = now
                self.engine.on_gap({"fromSeq": seq, "toSeq": seq, "reason": "local_queue_overflow"})
                self._status("채팅 처리량 초과 · 문제 안전 마감")

    def _on_message(self, generation: int, ws, text: str) -> None:
        if generation != self._generation:
            return
        now = time.monotonic()
        with self._diag_lock:
            self.last_frame_monotonic = now
        try:
            message = json.loads(text)
        except Exception:
            return
        kind = str(message.get("type") or "")

        # Event frames take the optimized path and do not call the v3 handler.
        if kind == "event":
            seq = int(message.get("seq") or 0)
            event = message.get("event") or {}
            if seq <= 0 or not isinstance(event, dict):
                return
            with self._diag_lock:
                self.event_count += 1
                self.last_event_monotonic = now
                self.last_event_epoch = time.time()
            self.current_seq = max(self.current_seq, seq)
            self.last_event_seq = max(self.last_event_seq, seq)
            self._enqueue_event(generation, seq, event)
            return

        if kind == "pong":
            with self._diag_lock:
                self.pong_count += 1
                self.last_pong_monotonic = now
            current = message.get("seq")
            if isinstance(current, int):
                self.current_seq = max(self.current_seq, current)
            return

        if kind == "resumed":
            with self._diag_lock:
                self.last_resumed_replayed = int(message.get("replayed") or 0)
            current = message.get("currentSeq")
            if isinstance(current, int):
                self.current_seq = max(self.current_seq, current)
            return

        super()._on_message(generation, ws, text)

    def diagnostics(self) -> dict[str, Any]:
        d = super().diagnostics()
        with self._diag_lock:
            pong_age = None
            if self.last_pong_monotonic > 0:
                pong_age = max(0.0, time.monotonic() - self.last_pong_monotonic)
            qsize = self._event_queue.qsize()
            if d["subscribed"] and self._worker.is_alive() and self.queue_drop_count == 0:
                pipeline = "정상"
            elif self.queue_drop_count > 0:
                pipeline = "주의"
            else:
                pipeline = "대기"
            d.update({
                "pipelineHealth": pipeline,
                "queueDepth": qsize,
                "queuePeak": self.queue_peak,
                "queueDrops": self.queue_drop_count,
                "processedEventCount": self.processed_event_count,
                "workerAlive": self._worker.is_alive(),
                "pingCount": self.ping_count,
                "pongCount": self.pong_count,
                "lastPongAgeSec": pong_age,
                "lastResumeReplayed": self.last_resumed_replayed,
            })
        return d

    def shutdown(self) -> None:
        self.disconnect(wait=False)
        self._heartbeat_stop.set()
        self._worker_stop.set()
