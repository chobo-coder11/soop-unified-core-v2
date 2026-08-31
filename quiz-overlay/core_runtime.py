from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Optional

from common import app_data_dir


class CoreRuntimeError(RuntimeError):
    pass


class BundledCoreRuntime:
    """Starts the Node-based Unified Core bundled inside the single EXE.

    End users do not need Node.js, npm, Java or a terminal. PyInstaller extracts
    the runtime into its temporary bundle directory and this class launches it
    hidden in the background with the Java sidecar disabled.
    """

    def __init__(self, preferred_port: int = 18765) -> None:
        self.preferred_port = preferred_port
        self.port = preferred_port
        self.process: Optional[subprocess.Popen] = None
        self.status = "준비 중"
        self.error = ""
        self.ready = False
        self._log_handle = None
        self._lock = threading.RLock()

    @staticmethod
    def bundle_root() -> Path:
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            return Path(getattr(sys, "_MEIPASS"))
        return Path(__file__).resolve().parent

    @classmethod
    def runtime_dir(cls) -> Path:
        return cls.bundle_root() / "runtime-core"

    @property
    def ws_url(self) -> str:
        return f"ws://127.0.0.1:{self.port}/v1/ws"

    @property
    def health_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/readyz"

    def _find_port(self) -> int:
        for port in range(self.preferred_port, self.preferred_port + 20):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.bind(("127.0.0.1", port))
                except OSError:
                    continue
                return port
        raise CoreRuntimeError("내부 엔진이 사용할 빈 포트를 찾지 못했습니다. 프로그램을 다시 실행해주세요.")

    def start(self, timeout: float = 18.0) -> None:
        with self._lock:
            if self.process and self.process.poll() is None and self.ready:
                return
            self.ready = False
            self.error = ""
            self.status = "내부 엔진 시작 중"
            runtime = self.runtime_dir()
            node = runtime / "node.exe"
            entry = runtime / "dist" / "src" / "index.js"
            package = runtime / "package.json"
            if not node.exists() or not entry.exists() or not package.exists():
                raise CoreRuntimeError("내부 방송 엔진 파일이 없습니다. 공식 배포 EXE를 다시 받아주세요.")

            self.port = self._find_port()
            env = os.environ.copy()
            env.update({
                "HOST": "127.0.0.1",
                "PORT": str(self.port),
                "SOOP_ENABLE_JAVA_SIDECAR": "false",
                "SOOP_ENABLE_WRITE_API": "false",
                "SOOP_ENABLE_SOOPJS_PROVIDER": "false",
                "SOOP_ENABLE_REINDEER_EVENTS": "false",
                "SOOP_ALLOW_INSECURE_TLS": "false",
                "SOOP_WS_REPLAY_EVENTS": "10000",
                "SOOP_WS_CLIENT_IDLE_MS": "120000",
            })
            log_path = app_data_dir() / "core-runtime.log"
            self._log_handle = log_path.open("a", encoding="utf-8", errors="replace")
            self._log_handle.write("\n--- bundled core start ---\n")
            self._log_handle.flush()
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            try:
                self.process = subprocess.Popen(
                    [str(node), str(entry)],
                    cwd=str(runtime),
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=self._log_handle,
                    stderr=self._log_handle,
                    creationflags=creationflags,
                )
            except Exception as exc:
                self.status = "엔진 시작 실패"
                self.error = str(exc)
                raise CoreRuntimeError(f"내부 방송 엔진을 시작하지 못했습니다: {exc}") from exc

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process and self.process.poll() is not None:
                self.status = "엔진 종료됨"
                self.error = f"내부 엔진이 예기치 않게 종료되었습니다. 코드 {self.process.returncode}"
                raise CoreRuntimeError(self.error)
            try:
                with urllib.request.urlopen(self.health_url, timeout=0.7) as response:
                    if 200 <= int(response.status) < 300:
                        self.ready = True
                        self.status = "준비 완료"
                        return
            except Exception:
                time.sleep(0.18)
        self.status = "엔진 응답 없음"
        self.error = "내부 방송 엔진이 준비 시간 안에 응답하지 않았습니다."
        self.stop()
        raise CoreRuntimeError(self.error)

    def start_async(self, on_done=None) -> threading.Thread:
        def run() -> None:
            error = None
            try:
                self.start()
            except Exception as exc:
                error = exc
            if on_done:
                try:
                    on_done(error)
                except Exception:
                    pass

        thread = threading.Thread(target=run, daemon=True, name="bundled-core-start")
        thread.start()
        return thread

    def stop(self) -> None:
        with self._lock:
            process = self.process
            self.process = None
            self.ready = False
            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=3)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass
            if self._log_handle:
                try:
                    self._log_handle.flush()
                    self._log_handle.close()
                except Exception:
                    pass
                self._log_handle = None
            self.status = "종료됨"
