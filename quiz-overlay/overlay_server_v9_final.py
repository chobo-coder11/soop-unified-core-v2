from __future__ import annotations

import json
import socket
import threading
import urllib.parse
from http.server import ThreadingHTTPServer

import overlay_server_v9_release as release
from quiz_engine_v9 import QuizEngineV9, UI_VERSION


# The base layer remains the single visual source. This final transport wrapper
# removes the blank-first-paint failure mode by bootstrapping the current safe
# public state into the HTML response itself. SSE still carries all later state.
FINAL_QUIZ = release.QUIZ
FINAL_QUIZ = FINAL_QUIZ.replace(
    '<main id="card" class="card"><div id="content"></div></main>',
    '<main id="card" class="card"><div id="content"><div class="hero"><div class="k">SOOP LIVE QUIZ</div><div class="t">연결 중</div><div class="s">현재 퀴즈 상태를 불러오고 있습니다</div></div></div></main>',
)
FINAL_QUIZ = FINAL_QUIZ.replace(
    "const C=document.querySelector('#content'),CARD=document.querySelector('#card'),W=document.querySelector('#warn'),NET=document.querySelector('#net');let S=null,scene='',tm=0,es=null;",
    "const C=document.querySelector('#content'),CARD=document.querySelector('#card'),W=document.querySelector('#warn'),NET=document.querySelector('#net');const INITIAL=__INITIAL_STATE_JSON__;let S=null,scene='',tm=0,es=null;",
)
FINAL_QUIZ = FINAL_QUIZ.replace(
    "sync().then(events);",
    "try{apply(INITIAL)}catch(e){NET.classList.remove('hidden')}events();setTimeout(sync,500);",
)
if '__INITIAL_STATE_JSON__' not in FINAL_QUIZ:
    raise RuntimeError('v0.9 final overlay bootstrap placeholder missing')


class HandlerV9Final(release.HandlerV9):
    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in {'/', '/overlay/quiz'}:
            # ensure_ascii keeps the script source portable even in older CEF.
            # Explicit HTML-sensitive escapes prevent a question string from
            # terminating the inline <script> element.
            raw = json.dumps(self.engine.public_state(), ensure_ascii=True, separators=(',', ':'))
            raw = raw.replace('<', r'\u003c').replace('>', r'\u003e').replace('&', r'\u0026')
            body = FINAL_QUIZ.replace('__INITIAL_STATE_JSON__', raw).encode('utf-8')
            self._send(200, body, 'text/html; charset=utf-8')
            return
        super().do_GET()


class OverlayServerV9Final:
    def __init__(self, engine: QuizEngineV9, preferred_port: int = 8765) -> None:
        self.engine = engine
        self.port = self._find_port(preferred_port)
        bound_handler = type('BoundHandlerV9Final', (HandlerV9Final,), {'engine': engine})
        self.server = ThreadingHTTPServer(('127.0.0.1', self.port), bound_handler)
        self.server.daemon_threads = True
        self.thread: threading.Thread | None = None

    @staticmethod
    def _find_port(preferred: int) -> int:
        for port in range(preferred, preferred + 30):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                try:
                    sock.bind(('127.0.0.1', port))
                except OSError:
                    continue
                return port
        raise RuntimeError('방송 레이어용 빈 포트를 찾지 못했습니다.')

    @property
    def quiz_url(self) -> str:
        return f'http://127.0.0.1:{self.port}/overlay/quiz'

    @property
    def rank_url(self) -> str:
        return f'http://127.0.0.1:{self.port}/overlay/top10'

    @property
    def top3_url(self) -> str:
        return f'http://127.0.0.1:{self.port}/overlay/top3?limit=3'

    @property
    def status_url(self) -> str:
        return f'http://127.0.0.1:{self.port}/overlay/status'

    @property
    def health_url(self) -> str:
        return f'http://127.0.0.1:{self.port}/api/health'

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.2}, daemon=True, name='overlay-http-v9-final')
        self.thread.start()

    def is_healthy(self) -> bool:
        return bool(self.thread and self.thread.is_alive())

    def stop(self) -> None:
        try:
            self.server.shutdown()
            self.server.server_close()
        except Exception:
            pass
