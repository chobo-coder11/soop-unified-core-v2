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
            # Chat answers do not change the recovery payload until scoring is finalized.
            # Avoid touching disk on every accepted answer/UI state version.
            if signature == self._recovery_signature and now - self._recovery_last_write < 8.0:
                return
            self._path(SESSION_FILE).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            self._recovery_signature = signature
            self._recovery_last_write = now
        except Exception:
            pass


def main() -> None:
    QuizAppV31().mainloop()


if __name__ == "__main__":
    main()
