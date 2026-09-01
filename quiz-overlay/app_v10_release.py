from __future__ import annotations

import ctypes
import sys

from app_v10 import PRODUCT_NAME, QuizAppV10
from app_v8 import DANGER, GOOD


class QuizAppV10Release(QuizAppV10):
    """Release wrapper for v0.10 editor UX fixes.

    Normal form validation is deliberately inline. A missing prompt or answer
    should never open a modal that blocks the operator during quiz preparation.
    """

    def _save_editor_draft(self, *, validate: bool, refresh: bool = True) -> bool:
        if not self._editor_ready or self._editor_loading:
            return True
        rows = self.quiz_sets.get(self.active_set_name, [])
        if not rows:
            return False
        q = self._question_from_editor(rows[self._current_editor_index()])
        if validate:
            error = self._validate_editor_question(q)
            if error:
                if hasattr(self, "editor_status"):
                    self.editor_status.configure(text="확인 · " + error, text_color=DANGER)
                # Keep the user in the editor instead of interrupting them with
                # a blocking message box. This also makes keyboard-first editing
                # predictable and prevents accidental modal stacking.
                return False
        self._save_quiz_sets()
        self.engine.set_questions(self.quiz_sets[self.active_set_name])
        if refresh:
            self._refresh_editor_navigation()
        if hasattr(self, "editor_status"):
            self.editor_status.configure(text="저장됨", text_color=GOOD)
        return True


def _single_instance() -> bool:
    if sys.platform != "win32":
        return True
    try:
        kernel = ctypes.windll.kernel32
        handle = kernel.CreateMutexW(None, False, "SOOPQuizStudio-v0.10-single-instance")
        if not handle:
            return True
        return kernel.GetLastError() != 183
    except Exception:
        return True


def main() -> None:
    if not _single_instance():
        try:
            ctypes.windll.user32.MessageBoxW(
                0, "SOOP Quiz Studio가 이미 실행 중입니다.", PRODUCT_NAME, 0x40
            )
        except Exception:
            pass
        return
    QuizAppV10Release().mainloop()


if __name__ == "__main__":
    main()
