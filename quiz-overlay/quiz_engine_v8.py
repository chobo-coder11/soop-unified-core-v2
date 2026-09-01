from __future__ import annotations

from typing import Any

from quiz_engine_v7 import QuizEngineV7


UI_VERSION = "0.8.0"


class QuizEngineV8(QuizEngineV7):
    """v0.8 UI shell over the hardened v0.5+ quiz engine."""

    def public_state(self) -> dict[str, Any]:
        state = super().public_state()
        state.setdefault("app", {})["version"] = UI_VERSION
        return state
