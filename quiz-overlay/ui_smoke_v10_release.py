from __future__ import annotations

import os
import threading
import traceback

import app_v9
from app_v10_release import QuizAppV10Release


def _hard_timeout() -> None:
    print("SMOKE_RELEASE: TIMEOUT", flush=True)
    os._exit(124)


def mark(text: str) -> None:
    print("SMOKE_RELEASE: " + text, flush=True)


def main() -> None:
    # Embedded Core is covered by dedicated workflow steps and the packaged EXE
    # smoke. Keep this test focused on real desktop editor widgets/interactions.
    app_v9.BundledCoreRuntime.start_async = lambda self, callback: None
    timer = threading.Timer(30.0, _hard_timeout)
    timer.daemon = True
    timer.start()
    app = None
    try:
        app = QuizAppV10Release()
        app.update_idletasks()
        app.show_page("문제")
        app.update_idletasks()
        assert app._active_page == "문제"
        assert app.nav_buttons["문제"].cget("text") == "문제 만들기"
        assert hasattr(app, "question_list")
        assert hasattr(app, "multiple_answer_menu")

        # Q1 draft must survive creating Q2 without a save dialog.
        app.prompt_box.delete("1.0", "end")
        app.prompt_box.insert("1.0", "자동 저장 확인 문제")
        app.add_question()
        app.update_idletasks()
        assert app.quiz_sets[app.active_set_name][0].prompt == "자동 저장 확인 문제"
        assert app._current_editor_index() == 1

        # A blank Q2 should fail validation INLINE, not open a modal or hang.
        assert app.save_current_question() is False
        assert "문제 내용을" in str(app.editor_status.cget("text"))
        mark("inline validation ok")

        # Fill Q2, switch its type, and save through the real widgets.
        app.prompt_box.delete("1.0", "end")
        app.prompt_box.insert("1.0", "대한민국의 수도는?")
        app.kind_var.set("주관식")
        app._editor_type_changed()
        app.update_idletasks()
        assert app.short_card.winfo_ismapped()
        assert not app.choice_card.winfo_ismapped()
        app.short_answer_var.set("서울")
        assert app.save_current_question() is True
        assert app.quiz_sets[app.active_set_name][1].kind == "short"
        assert app.quiz_sets[app.active_set_name][1].answer == "서울"
        assert app.quiz_sets[app.active_set_name][1].prompt == "대한민국의 수도는?"

        # Navigate back: the list and editor must keep the saved Q1/Q2 values.
        app._select_editor_question(0)
        app.update_idletasks()
        assert "자동 저장 확인 문제" in app.prompt_box.get("1.0", "end")
        app._select_editor_question(1)
        app.update_idletasks()
        assert app.kind_var.get() == "주관식"
        assert app.short_answer_var.get() == "서울"

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
