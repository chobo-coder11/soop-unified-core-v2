from __future__ import annotations

import json
import queue
from dataclasses import asdict
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import ttk

from common import APP_NAME, APP_VERSION, DEFAULT_PORT, QUIZ_FILE, SETTINGS_FILE, Question, app_data_dir
from engine import QuizEngine, CoreSocketClient
from overlays import OverlayServer
from ui_run import RunMixin
from ui_edit import EditMixin

class App(RunMixin, EditMixin, tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1180x760")
        self.minsize(980, 680)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.engine = QuizEngine()
        self.event_queue: queue.Queue[str] = queue.Queue()
        self.core = CoreSocketClient(self.engine, self.event_queue)
        self.port = DEFAULT_PORT
        self.server = OverlayServer(self.engine, self.port)
        self.server.start()
        self.settings = self.load_json(SETTINGS_FILE, {})
        self.quiz_sets: dict[str, list[Question]] = self.load_quiz_sets()
        self.active_set_name = next(iter(self.quiz_sets.keys()), "기본 퀴즈")
        self.engine.questions = self.quiz_sets.get(self.active_set_name, [self.sample_question()])
        self._build_ui()
        self.after(150, self.refresh_ui)

    def sample_question(self) -> Question:
        return Question(prompt="샘플 문제: 2 + 2는?", choices=["3", "4", "5", "6"], answer="2")

    def path(self, name: str) -> Path:
        return app_data_dir() / name

    def load_json(self, name: str, default: Any) -> Any:
        try:
            return json.loads(self.path(name).read_text(encoding="utf-8"))
        except Exception:
            return default

    def load_quiz_sets(self) -> dict[str, list[Question]]:
        raw = self.load_json(QUIZ_FILE, {})
        out: dict[str, list[Question]] = {}
        if isinstance(raw, dict):
            for name, rows in raw.items():
                if isinstance(rows, list):
                    out[str(name)] = [Question.from_dict(x) for x in rows if isinstance(x, dict)]
        if not out:
            out["기본 퀴즈"] = [self.sample_question()]
        return out

    def save_quiz_sets(self) -> None:
        data = {name: [asdict(q) for q in qs] for name, qs in self.quiz_sets.items()}
        self.path(QUIZ_FILE).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except Exception:
            pass
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        top = ttk.Frame(root)
        top.pack(fill="x")
        self.status_var = tk.StringVar(value="● 연결 안 됨")
        ttk.Label(top, text=APP_NAME, font=("Malgun Gothic", 17, "bold")).pack(side="left")
        ttk.Label(top, textvariable=self.status_var, font=("Malgun Gothic", 10, "bold")).pack(side="right")

        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="both", expand=True, pady=(10, 0))
        self.tab_run = ttk.Frame(self.tabs, padding=14)
        self.tab_edit = ttk.Frame(self.tabs, padding=14)
        self.tab_layer = ttk.Frame(self.tabs, padding=14)
        self.tabs.add(self.tab_run, text="진행")
        self.tabs.add(self.tab_edit, text="문제 편집")
        self.tabs.add(self.tab_layer, text="레이어")
        self.build_run_tab()
        self.build_edit_tab()
        self.build_layer_tab()

    def on_close(self) -> None:
        try: self.core.disconnect()
        except Exception: pass
        try: self.server.stop()
        except Exception: pass
        self.destroy()


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
