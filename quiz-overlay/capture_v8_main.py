from __future__ import annotations

import ctypes
import time
from pathlib import Path

from PIL import ImageGrab


user32 = ctypes.windll.user32
WM_CLOSE = 0x0010
CALLBACK = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)


def title_of(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if not length:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def visible_windows() -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []

    @CALLBACK
    def enum_cb(hwnd, _param):
        if user32.IsWindowVisible(hwnd):
            title = title_of(hwnd)
            if title:
                found.append((int(hwnd), title))
        return True

    user32.EnumWindows(enum_cb, 0)
    return found


def main() -> None:
    # Close the first-run guide so visual QA inspects the actual controller.
    for hwnd, title in visible_windows():
        if title == "SOOP Quiz Studio 시작하기":
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)

    time.sleep(2.0)
    targets = [
        (hwnd, title)
        for hwnd, title in visible_windows()
        if "SOOP Quiz Studio" in title and "시작하기" not in title
    ]
    if not targets:
        raise SystemExit("Main SOOP Quiz Studio window not found")

    hwnd, title = targets[0]
    try:
        image = ImageGrab.grab(window=hwnd)
    except (TypeError, OSError):
        rect = (ctypes.c_long * 4)()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            raise SystemExit("Could not read main window rectangle")
        bbox = tuple(int(v) for v in rect)
        image = ImageGrab.grab(bbox=bbox, all_screens=True)

    output = Path(__file__).with_name("v8-main-window.png")
    image.save(output)
    print(f"Captured {title!r}: {image.size[0]}x{image.size[1]} -> {output}")


if __name__ == "__main__":
    main()
