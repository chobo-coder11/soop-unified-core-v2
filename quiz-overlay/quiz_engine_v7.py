from __future__ import annotations

from typing import Any

from quiz_engine_v6 import QuizEngineV6


UI_VERSION = "0.7.0"


class QuizEngineV7(QuizEngineV6):
    """v0.7 product UI wrapper.

    Scoring, participant tracking and ordering semantics stay inherited from the
    hardened v0.5/v0.6 engine. v0.7 advances only the controller/overlay product
    version so the UX redesign cannot destabilize quiz accuracy.
    """

    def public_state(self) -> dict[str, Any]:
        state = super().public_state()
        state.setdefault("app", {})["version"] = UI_VERSION
        return state
