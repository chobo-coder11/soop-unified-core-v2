from __future__ import annotations

import os
import threading
import traceback

import app_v9
from app_v10 import QuizAppV10


def _hard_timeout() -> None:
    print("SMOKE: TIMEOUT", flush=True)
    os._exit(124)


def mark(text: str) -> None:
    print("SMOKE: " + text, flush=True)


def main() -> None:
    # The UI interaction test is about desktop widgets/editor behavior, not the
    # embedded Node process. Keep that separate; the workflow has dedicated
    # Core and final packaged-EXE smoke gates.
    app_v9.BundledCoreRuntime.start_async = lambda self, callback: None
    timer = threading.Timer(30.0, _hard_timeout)
    timer.daemon = True
    timer.start()
    app = None
    try:
        mark("before app")
        app = QuizAppV10()
        mark("after app")
        app.update_idletasks()
        mark("after initial idle")
        app.show_page("문제")
        mark("after show editor")
        app.update_idletasks()
        mark("after editor idle")
        assert app._active_page == "문제"
        assert app.nav_buttons["문제"].cget("text") == "문제 만들기"
        assert hasattr(app, "question_list")
        assert hasattr(app, "multiple_answer_menu")
        assert hasattr(app, "editor_status")

        app.prompt_box.delete("1.0", "end")
        app.prompt_box.insert("1.0", "자동 저장 확인 문제")
        mark("before add")
        app.add_question()
        mark("after add")
        app.update_idletasks()
        assert app.quiz_sets[app.active_set_name][0].prompt == "자동 저장 확인 문제"
        assert app._current_editor_index() == 1

        app.kind_var.set("주관식")
        app._editor_type_changed()
        app.update_idletasks()
        mark("after kind switch")
        assert app.short_card.winfo_ismapped()
        assert not app.choice_card.winfo_ismapped()

        app.short_answer_var.set("서울")
        assert app.save_current_question()
        mark("after save")
        assert app.quiz_sets[app.active_set_name][1].kind == "short"
        assert app.quiz_sets[app.active_set_name][1].answer == "서울"

        mark("PASS")
        try:
            app.destroy()
        except Exception:
            pass
        timer.cancel()
        os._exit(0)
    except BaseException:
        traceback.print_exc()
        try:
            if app is not None:
                app.destroy()
        except Exception:
            pass
        timer.cancel()
        os._exit(1)


if __name__ == "__main__":
    main()
