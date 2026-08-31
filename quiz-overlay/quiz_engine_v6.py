from __future__ import annotations

from typing import Any

from quiz_engine_v5 import QuizEngineV5


UI_VERSION = "0.6.0"


class QuizEngineV6(QuizEngineV5):
    """Presentation-focused v0.6 wrapper.

    The quiz/scoring engine stays identical to v0.5; only the product version
    exposed to the controller/overlays is advanced for the design rebuild.
    """

    def public_state(self) -> dict[str, Any]:
        state = super().public_state()
        state.setdefault("app", {})["version"] = UI_VERSION
        return state
