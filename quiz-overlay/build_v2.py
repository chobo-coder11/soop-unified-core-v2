from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import PyInstaller.__main__


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DIST_SRC = ROOT / "dist" / "src"
NODE_MODULES = ROOT / "node_modules"
PACKAGE_JSON = ROOT / "package.json"
NODE = shutil.which("node")


def add(source: Path | str, dest: str) -> str:
    return f"{source}{os.pathsep}{dest}"


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("This packaging script must run on Windows.")
    if not NODE:
        raise SystemExit("node.exe not found in PATH")
    node_path = Path(NODE).resolve()
    required = [DIST_SRC / "index.js", NODE_MODULES, PACKAGE_JSON, HERE / "app_v2.py"]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise SystemExit("Missing build inputs: " + ", ".join(missing))

    args = [
        str(HERE / "app_v2.py"),
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name=SOOP-Quiz-Overlay",
        f"--distpath={HERE / 'dist'}",
        f"--workpath={HERE / 'build'}",
        f"--specpath={HERE}",
        f"--paths={HERE}",
        "--collect-all=customtkinter",
        "--hidden-import=websocket",
        "--hidden-import=customtkinter",
        "--add-binary=" + add(node_path, "runtime-core"),
        "--add-data=" + add(DIST_SRC, "runtime-core/dist/src"),
        "--add-data=" + add(NODE_MODULES, "runtime-core/node_modules"),
        "--add-data=" + add(PACKAGE_JSON, "runtime-core"),
    ]
    PyInstaller.__main__.run(args)

    exe = HERE / "dist" / "SOOP-Quiz-Overlay.exe"
    if not exe.exists() or exe.stat().st_size < 10_000_000:
        raise SystemExit("EXE output missing or unexpectedly small")
    print(f"Built: {exe} ({exe.stat().st_size / 1024 / 1024:.1f} MiB)")


if __name__ == "__main__":
    main()
