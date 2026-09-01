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
    required = [
        DIST_SRC / "index.js", NODE_MODULES, PACKAGE_JSON,
        HERE / "app_v10_release.py", HERE / "app_v10.py", HERE / "app_v9.py", HERE / "app_v8.py", HERE / "app_v7.py", HERE / "app_v6.py", HERE / "app_v5.py", HERE / "app_v4.py", HERE / "app_v31.py", HERE / "app_v3.py",
        HERE / "quiz_engine_v10.py", HERE / "quiz_engine_v9.py", HERE / "quiz_engine_v8.py", HERE / "quiz_engine_v7.py", HERE / "quiz_engine_v6.py", HERE / "quiz_engine_v5.py", HERE / "quiz_engine_v4.py", HERE / "quiz_engine_v3.py",
        HERE / "soop_client_v5.py", HERE / "soop_client_v4.py", HERE / "soop_client_v3.py",
        HERE / "overlay_server_v10.py", HERE / "overlay_server_v9_final.py", HERE / "overlay_server_v9_release.py", HERE / "overlay_server_v9.py", HERE / "overlay_server_v8.py", HERE / "overlay_server_v7.py", HERE / "overlay_server_v6.py", HERE / "overlay_server_v5.py",
        HERE / "core_runtime.py", HERE / "common.py",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise SystemExit("Missing build inputs: " + ", ".join(missing))

    args = [
        str(HERE / "app_v10_release.py"), "--noconfirm", "--clean", "--onefile", "--windowed", "--noupx",
        "--name=SOOP-Quiz-Studio-v0.10.0",
        f"--distpath={HERE / 'dist-v10-release'}", f"--workpath={HERE / 'build-v10-release'}", f"--specpath={HERE}", f"--paths={HERE}",
        "--collect-all=customtkinter", "--hidden-import=websocket", "--hidden-import=customtkinter",
        "--hidden-import=app_v10", "--hidden-import=app_v9", "--hidden-import=app_v8",
        "--hidden-import=overlay_server_v10", "--hidden-import=overlay_server_v9_final", "--hidden-import=overlay_server_v9_release", "--hidden-import=overlay_server_v9",
        "--hidden-import=quiz_engine_v10", "--hidden-import=quiz_engine_v9", "--hidden-import=quiz_engine_v8", "--hidden-import=quiz_engine_v7", "--hidden-import=quiz_engine_v6", "--hidden-import=quiz_engine_v5",
        "--hidden-import=soop_client_v5", "--hidden-import=overlay_server_v8", "--hidden-import=overlay_server_v7", "--hidden-import=overlay_server_v6", "--hidden-import=overlay_server_v5",
        "--add-binary=" + add(node_path, "runtime-core"),
        "--add-data=" + add(DIST_SRC, "runtime-core/dist/src"),
        "--add-data=" + add(NODE_MODULES, "runtime-core/node_modules"),
        "--add-data=" + add(PACKAGE_JSON, "runtime-core"),
    ]
    PyInstaller.__main__.run(args)
    exe = HERE / "dist-v10-release" / "SOOP-Quiz-Studio-v0.10.0.exe"
    if not exe.exists() or exe.stat().st_size < 10_000_000:
        raise SystemExit("EXE output missing or unexpectedly small")
    print(f"Built release: {exe} ({exe.stat().st_size / 1024 / 1024:.1f} MiB)")


if __name__ == "__main__":
    main()
