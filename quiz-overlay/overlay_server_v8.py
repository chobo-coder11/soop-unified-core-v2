from __future__ import annotations

from overlay_server_v7 import OverlayServerV7
from quiz_engine_v8 import QuizEngineV8


class OverlayServerV8(OverlayServerV7):
    """Keep the proven SSE/browser layer while exposing the v0.8 engine state."""

    def __init__(self, engine: QuizEngineV8, preferred_port: int = 8765) -> None:
        super().__init__(engine, preferred_port)
