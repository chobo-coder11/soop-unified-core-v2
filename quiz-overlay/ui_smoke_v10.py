from __future__ import annotations

import os
import threading
import traceback

from app_v10 import QuizAppV10


def _hard_timeout() -> None:
    print("v0.10 desktop editor smoke timed out", flush=True)
    os._exit(124)


def main() -> None:
    timer = threading.Timer(30.0, _hard_timeout)
    timer.daemon = True
    timer.start()
    app = None
    try:
        app = QuizAppV10()
        app.update_idletasks()
        app.show_page("문제")
        app.update_idletasks()
        assert app._active_page == "문제"
        assert app.nav_buttons["문제"].cget("text") == "문제 만들기"
        assert hasattr(app, "question_list")
        assert hasattr(app, "multiple_answer_menu")
        assert hasattr(app, "editor_status")

        # Draft-loss regression: editing Q1 and pressing + new question must
        # persist Q1 without requiring a modal save first.
        app.prompt_box.delete("1.0", "end")
        app.prompt_box.insert("1.0", "자동 저장 확인 문제")
        app.add_question()
        app.update_idletasks()
        assert app.quiz_sets[app.active_set_name][0].prompt == "자동 저장 확인 문제"
        assert app._current_editor_index() == 1

        # The editor must actually switch the visible answer form by quiz type.
        app.kind_var.set("주관식")
        app._editor_type_changed()
        app.update_idletasks()
        assert app.short_card.winfo_ismapped()
        assert not app.choice_card.winfo_ismapped()

        app.short_answer_var.set("서울")
        assert app.save_current_question()
        assert app.quiz_sets[app.active_set_name][1].kind == "short"
        assert app.quiz_sets[app.active_set_name][1].answer == "서울"

        print("v0.10 desktop editor interaction smoke passed", flush=True)
        # Do not let a background Tk/HTTP/runtime cleanup edge case turn a
        # successful interaction regression into an indefinite CI process.
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
