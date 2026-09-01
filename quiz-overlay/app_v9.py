from __future__ import annotations

import ctypes
import sys
import time

import customtkinter as ctk
from tkinter import messagebox

from app_v8 import BG, PRODUCT_NAME, QuizAppV8
from common import SESSION_FILE, SETTINGS_FILE
from core_runtime import BundledCoreRuntime
from overlay_server_v9 import OverlayServerV9
from quiz_engine_v9 import QuizEngineV9, UI_VERSION
from soop_client_v5 import SoopChatClientV5


class QuizAppV9(QuizAppV8):
    """v0.9 hot path hardening for problem reveal and live quiz operation."""

    def __init__(self) -> None:
        ctk.set_widget_scaling(1.0)
        self._recovery_last_write = 0.0
        self._recovery_signature = None
        self.settings = self._load_json(SETTINGS_FILE, {})
        appearance = str(self.settings.get("appearance", "dark")).lower()
        ctk.set_appearance_mode({"light": "Light", "system": "System"}.get(appearance, "Dark"))
        ctk.set_default_color_theme("blue")
        ctk.CTk.__init__(self)
        self.title(f"{PRODUCT_NAME} · v{UI_VERSION}")
        self.geometry("1480x900")
        self.minsize(1180, 720)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.engine = QuizEngineV9()
        self.runtime = BundledCoreRuntime()
        self.client = SoopChatClientV5(self.engine, self._socket_status)
        self.overlay = OverlayServerV9(self.engine)
        self.overlay.start()

        self.quiz_sets = self._load_quiz_sets()
        self.active_set_name = str(self.settings.get("active_set") or next(iter(self.quiz_sets)))
        if self.active_set_name not in self.quiz_sets:
            self.active_set_name = next(iter(self.quiz_sets))
        self.engine.set_questions(self.quiz_sets[self.active_set_name])
        self.engine.ranking_mode = str(self.settings.get("ranking_mode", "correct_count"))
        self.engine.set_allow_mid_join(bool(self.settings.get("allow_mid_join", False)))
        self.engine.set_visual(
            theme=str(self.settings.get("overlay_theme", "dark")),
            motion=bool(self.settings.get("overlay_motion", True)),
            compact_ranking=bool(self.settings.get("compact_ranking", False)),
            show_fastest=bool(self.settings.get("show_fastest", True)),
        )
        with self.engine.lock:
            self.engine.visual["style"] = str(self.settings.get("overlay_style", "clean"))
            self.engine.visual["accent"] = str(self.settings.get("overlay_accent", "#5b7cff"))

        self._runtime_error = ""
        self._active_page = "진행"
        self._pages: dict[str, ctk.CTkFrame] = {}
        self._last_ui_version = -1
        self._last_chat_version = -1
        self._last_diag = ""
        self._pending_recovery = self._load_json(SESSION_FILE, {})
        self._closing = False
        self._core_restart_pending = False
        self._watchdog_failures = 0
        self.live_mode_var = ctk.BooleanVar(value=False)
        self._last_primary_action_at = 0.0

        self._build_shell()
        self.show_page("진행")
        self._bind_hotkeys()
        self.bind("<F9>", lambda _e: self._toggle_live_mode_hotkey())
        self.after(100, self._ui_tick)
        self.after(2500, self._watchdog_tick)
        self.after(10000, self._checkpoint_tick)
        self.runtime.start_async(lambda err: self.after(0, lambda: self._runtime_finished(err)))
        # Reuse the concise v0.8 onboarding; its completion flag prevents repeats.
        if not self.settings.get("onboarding_done_v8"):
            self.after(450, self.show_onboarding)

    @staticmethod
    def _stage_info(state: str) -> tuple[str, str, str]:
        mapping = {
            "DISCONNECTED": ("OFFLINE", "연결 대기", "방송 연결"),
            "READY": ("READY", "방송 연결 완료", "참가 모집 시작"),
            "RECRUITING": ("RECRUITING", "참가 모집 중", "참가 마감"),
            "LOCKED": ("QUESTION", "문제 준비", "문제 공개"),
            "QUESTION_SHOWN": ("QUESTION OPEN", "문제 공개 · 답변 대기", "START · 답변 시작"),
            "ANSWERING": ("LIVE", "답변 접수 중", "답변 마감"),
            "QUESTION_CLOSED": ("CLOSED", "답변 마감", "정답 공개"),
            "ANSWER_REVEALED": ("RESULT", "정답 공개", "다음 문제"),
            "QUESTION_VOID": ("VOID", "문제 무효", "다음 문제"),
            "FINISHED": ("FINAL", "퀴즈 종료", "새 참가 모집"),
        }
        return mapping.get(state, (state, state, "진행"))

    def primary_action(self) -> None:
        # Prevent a mouse double-click / Space key-repeat from skipping
        # QUESTION_SHOWN and immediately opening answers.
        now = time.monotonic()
        if now - self._last_primary_action_at < 0.42:
            return
        self._last_primary_action_at = now

        before = self.engine.state
        ok = False
        if before == "DISCONNECTED":
            self._flash_top("먼저 방송을 연결하거나 연습 모드를 켜주세요.", "#D9952B")
            return
        if before in {"READY", "FINISHED"}:
            if not self.engine.questions:
                messagebox.showwarning("문제 없음", "참가 모집 전에 문제를 하나 이상 만들어주세요.")
                return
            ok = self.engine.start_recruitment()
        elif before == "RECRUITING":
            ok = self.engine.close_recruitment()
        elif before == "LOCKED":
            error = self.engine.current_question_error()
            if error:
                messagebox.showwarning("문제 공개 불가", error)
                return
            ok = self.engine.show_question()
        elif before == "QUESTION_SHOWN":
            ok = self.engine.open_answers(self.client.current_seq)
        elif before == "ANSWERING":
            ok = self.engine.close_answers()
        elif before == "QUESTION_CLOSED":
            ok = self.engine.reveal_answer()
        elif before in {"ANSWER_REVEALED", "QUESTION_VOID"}:
            ok = self.engine.next_question()

        if not ok:
            reason = getattr(self.engine, "last_transition_error", "") or "현재 단계에서는 이 동작을 실행할 수 없습니다."
            self._flash_top(reason, "#D9952B")
            return

        # Recruitment is the point at which dangerous editing controls should lock.
        if before in {"READY", "FINISHED"} and self.engine.state == "RECRUITING" and not self.engine.practice_mode:
            self._set_live_mode(True)

        self._last_ui_version = -1
        self.after(0, lambda: self._refresh_active_page(force=True) if not self._closing else None)


def _single_instance() -> bool:
    if sys.platform != "win32":
        return True
    try:
        kernel = ctypes.windll.kernel32
        handle = kernel.CreateMutexW(None, False, "SOOPQuizStudio-v0.9-single-instance")
        if not handle:
            return True
        return kernel.GetLastError() != 183
    except Exception:
        return True


def main() -> None:
    if not _single_instance():
        try:
            ctypes.windll.user32.MessageBoxW(0, "SOOP Quiz Studio가 이미 실행 중입니다.", "SOOP Quiz Studio", 0x40)
        except Exception:
            pass
        return
    QuizAppV9().mainloop()


if __name__ == "__main__":
    main()
