from __future__ import annotations

# Import the final overlay transport before constructing the v0.9 app. It keeps
# the release viewport/JS hotfixes, bootstraps the current public quiz state into
# the first HTML response, and then uses SSE for subsequent state changes.
from overlay_server_v9_final import OverlayServerV9Final
import app_v9

# QuizAppV9 resolves OverlayServerV9 from its module global at construction time.
# Swap only that dependency; the rest of the controller stays on the tested v0.9
# implementation.
app_v9.OverlayServerV9 = OverlayServerV9Final


def main() -> None:
    app_v9.main()


if __name__ == "__main__":
    main()
