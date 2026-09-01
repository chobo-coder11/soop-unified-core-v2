from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from pathlib import Path

from PIL import Image


user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
WM_CLOSE = 0x0010
PW_RENDERFULLCONTENT = 0x00000002
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
DIB_RGB_COLORS = 0
BI_RGB = 0


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


CALLBACK = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)


def title_of(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if not length:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def windows() -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []

    @CALLBACK
    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            title = title_of(hwnd)
            if title:
                out.append((int(hwnd), title))
        return True

    user32.EnumWindows(cb, 0)
    return out


def capture(hwnd: int, width: int, height: int) -> Image.Image:
    # Force the native top-level window to the same dimensions used by the app
    # even on GitHub's small 1024x768 interactive desktop.
    user32.SetWindowPos(hwnd, 0, 0, 0, width, height, SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE)
    time.sleep(1.0)

    window_dc = user32.GetWindowDC(hwnd)
    if not window_dc:
        raise RuntimeError("GetWindowDC failed")
    mem_dc = gdi32.CreateCompatibleDC(window_dc)
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    old = gdi32.SelectObject(mem_dc, bitmap)
    try:
        ok = user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT)
        if not ok:
            ok = user32.PrintWindow(hwnd, mem_dc, 0)
        if not ok:
            raise RuntimeError("PrintWindow failed")

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB
        size = width * height * 4
        buf = ctypes.create_string_buffer(size)
        rows = gdi32.GetDIBits(mem_dc, bitmap, 0, height, buf, ctypes.byref(bmi), DIB_RGB_COLORS)
        if rows != height:
            raise RuntimeError(f"GetDIBits returned {rows}/{height} rows")
        return Image.frombuffer("RGB", (width, height), buf, "raw", "BGRX", 0, 1).copy()
    finally:
        gdi32.SelectObject(mem_dc, old)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(hwnd, window_dc)


def main() -> None:
    for hwnd, title in windows():
        if title == "SOOP Quiz Studio 시작하기":
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    time.sleep(1.5)

    targets = [
        (hwnd, title)
        for hwnd, title in windows()
        if "SOOP Quiz Studio" in title and "시작하기" not in title
    ]
    if not targets:
        raise SystemExit("Main SOOP Quiz Studio window not found")

    hwnd, title = targets[0]
    image = capture(hwnd, 1480, 900)
    output = Path(__file__).with_name("v8-full-window.png")
    image.save(output)
    print(f"Captured full window {title!r}: {image.size} -> {output}")


if __name__ == "__main__":
    main()
