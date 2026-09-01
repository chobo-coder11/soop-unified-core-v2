from __future__ import annotations

import ctypes
import sys

import customtkinter as ctk

from app_v9 import QuizAppV9, BG, PRODUCT_NAME, UI_VERSION
from common import SESSION_FILE, SETTINGS_FILE
from core_runtime import BundledCoreRuntime
from overlay_server_v9_final import OverlayServerV9Final
from quiz_engine_v9 import QuizEngineV9
from soop_client_v5 import SoopChatClientV5


class QuizAppV9Final(QuizAppV9):
    def __init__(self) -> None:
        ctk.set_widget_scaling(1.0)
        self._recovery_last_write = 0.0
        self._recovery_signature = None
        self.settings = self._load_json(SETTINGS_FILE, {})
        appearance = str(self.settings.get('appearance', 'dark')).lower()
        ctk.set_appearance_mode({'light': 'Light', 'system': 'System'}.get(appearance, 'Dark'))
        ctk.set_default_color_theme('blue')
        ctk.CTk.__init__(self)
        self.title(f'{PRODUCT_NAME} · v{UI_VERSION}')
        self.geometry('1480x900')
        self.minsize(1180, 720)
        self.configure(fg_color=BG)
        self.protocol('WM_DELETE_WINDOW', self.on_close)

        self.engine = QuizEngineV9()
        self.runtime = BundledCoreRuntime()
        self.client = SoopChatClientV5(self.engine, self._socket_status)
        self.overlay = OverlayServerV9Final(self.engine)
        self.overlay.start()

        self.quiz_sets = self._load_quiz_sets()
        self.active_set_name = str(self.settings.get('active_set') or next(iter(self.quiz_sets)))
        if self.active_set_name not in self.quiz_sets:
            self.active_set_name = next(iter(self.quiz_sets))
        self.engine.set_questions(self.quiz_sets[self.active_set_name])
        self.engine.ranking_mode = str(self.settings.get('ranking_mode', 'correct_count'))
        self.engine.set_allow_mid_join(bool(self.settings.get('allow_mid_join', False)))
        self.engine.set_visual(
            theme=str(self.settings.get('overlay_theme', 'dark')),
            motion=bool(self.settings.get('overlay_motion', True)),
            compact_ranking=bool(self.settings.get('compact_ranking', False)),
            show_fastest=bool(self.settings.get('show_fastest', True)),
        )
        with self.engine.lock:
            self.engine.visual['style'] = str(self.settings.get('overlay_style', 'clean'))
            self.engine.visual['accent'] = str(self.settings.get('overlay_accent', '#5b7cff'))

        self._runtime_error = ''
        self._active_page = '진행'
        self._pages: dict[str, ctk.CTkFrame] = {}
        self._last_ui_version = -1
        self._last_chat_version = -1
        self._last_diag = ''
        self._pending_recovery = self._load_json(SESSION_FILE, {})
        self._closing = False
        self._core_restart_pending = False
        self._watchdog_failures = 0
        self.live_mode_var = ctk.BooleanVar(value=False)
        self._last_primary_action_at = 0.0

        self._build_shell()
        self.show_page('진행')
        self._bind_hotkeys()
        self.bind('<F9>', lambda _e: self._toggle_live_mode_hotkey())
        self.after(100, self._ui_tick)
        self.after(2500, self._watchdog_tick)
        self.after(10000, self._checkpoint_tick)
        self.runtime.start_async(lambda err: self.after(0, lambda: self._runtime_finished(err)))
        if not self.settings.get('onboarding_done_v8'):
            self.after(450, self.show_onboarding)


def _single_instance() -> bool:
    if sys.platform != 'win32':
        return True
    try:
        kernel = ctypes.windll.kernel32
        handle = kernel.CreateMutexW(None, False, 'SOOPQuizStudio-v0.9-final-single-instance')
        if not handle:
            return True
        return kernel.GetLastError() != 183
    except Exception:
        return True


def main() -> None:
    if not _single_instance():
        try:
            ctypes.windll.user32.MessageBoxW(0, 'SOOP Quiz Studio가 이미 실행 중입니다.', 'SOOP Quiz Studio', 0x40)
        except Exception:
            pass
        return
    QuizAppV9Final().mainloop()


if __name__ == '__main__':
    main()
