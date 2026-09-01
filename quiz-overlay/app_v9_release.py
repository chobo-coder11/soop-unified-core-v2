from __future__ import annotations

# Must be imported before app_v9 so its OverlayServerV9 handler sees the corrected
# module-level QUIZ document used by the shipped EXE.
import overlay_server_v9_release  # noqa: F401
from app_v9 import main


if __name__ == "__main__":
    main()
