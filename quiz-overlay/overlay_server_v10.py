from __future__ import annotations

import json
import socket
import threading
import urllib.parse
from http.server import ThreadingHTTPServer

from overlay_server_v9_final import FINAL_QUIZ, HandlerV9Final
from quiz_engine_v10 import QuizEngineV10, UI_VERSION


class HandlerV10(HandlerV9Final):
    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/health":
            self._send(
                200,
                json.dumps({"ok": True, "version": UI_VERSION, "transport": "sse-v2"}, separators=(",", ":")).encode(),
                "application/json",
            )
            return
        super().do_GET()


class OverlayServerV10:
    def __init__(self, engine: QuizEngineV10, preferred_port: int = 8765) -> None:
        self.engine = engine
        self.port = self._find_port(preferred_port)
        bound_handler = type("BoundHandlerV10", (HandlerV10,), {"engine": engine})
        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), bound_handler)
        self.server.daemon_threads = True
        self.thread: threading.Thread | None = None

    @staticmethod
    def _find_port(preferred: int) -> int:
        for port in range(preferred, preferred + 30):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                try:
                    sock.bind(("127.0.0.1", port))
                except OSError:
                    continue
                return port
        raise RuntimeError("방송 레이어용 빈 포트를 찾지 못했습니다.")

    @property
    def quiz_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/overlay/quiz"

    @property
    def rank_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/overlay/top10"

    @property
    def top3_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/overlay/top3?limit=3"

    @property
    def status_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/overlay/status"

    @property
    def health_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/api/health"

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            kwargs={"poll_interval": 0.2},
            daemon=True,
            name="overlay-http-v10",
        )
        self.thread.start()

    def is_healthy(self) -> bool:
        return bool(self.thread and self.thread.is_alive())

    def stop(self) -> None:
        try:
            self.server.shutdown()
            self.server.server_close()
        except Exception:
            pass
