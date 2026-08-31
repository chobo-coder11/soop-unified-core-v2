from __future__ import annotations

import json
import time

from app_v3 import QuizAppV3
from common import SESSION_FILE


class QuizAppV31(QuizAppV3):
    def __init__(self) -> None:
        self._recovery_last_write = 0.0
        self._recovery_signature = None
        super().__init__()

    def _save_recovery(self) -> None:
        if not bool(self.settings.get("auto_recovery", True)):
            return
        try:
            payload = self.engine.recovery_state()
            payload["activeSet"] = self.active_set_name
            signature = (
                payload.get("questionIndex"),
                tuple(
                    (p.get("user_id"), p.get("correct_count"), p.get("score"), p.get("best_streak"))
                    for p in payload.get("participants", [])
                ),
            )
            now = time.monotonic()
            # Accepted answers do not alter the recovery payload until scoring is finalized.
            # Avoid disk I/O on every chat/UI state version.
            if signature == self._recovery_signature and now - self._recovery_last_write < 8.0:
                return
            self._path(SESSION_FILE).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            self._recovery_signature = signature
            self._recovery_last_write = now
        except Exception:
            pass

    def _ui_tick(self) -> None:
        super()._ui_tick()
        # Only this single label changes during the countdown. The rest of the
        # desktop console remains untouched until engine.state_version changes.
        if self._active_page == "진행" and self.engine.state == "ANSWERING" and hasattr(self, "stage_label"):
            remaining = self.engine.remaining_ms()
            if remaining is not None:
                self.stage_label.configure(text=f"답변 접수 중  ·  {remaining / 1000:.1f}초")


def main() -> None:
    QuizAppV31().mainloop()


if __name__ == "__main__":
    main()
