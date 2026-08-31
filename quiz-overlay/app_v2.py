from __future__ import annotations

import json
import os
import webbrowser
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

import customtkinter as ctk
from tkinter import messagebox

from common import APP_NAME, APP_VERSION, QUIZ_FILE, SETTINGS_FILE, Question, app_data_dir, safe_float, safe_int
from core_runtime import BundledCoreRuntime, CoreRuntimeError
from overlay_server_v2 import OverlayServer
from quiz_engine import QuizEngine
from soop_client import SoopChatClient


FONT = "Malgun Gothic"


class QuizApp(ctk.CTk):
    def __init__(self) -> None:
        self.settings = self._load_json(SETTINGS_FILE, {})
        appearance = str(self.settings.get("appearance", "dark")).lower()
        ctk.set_appearance_mode({"light": "Light", "system": "System"}.get(appearance, "Dark"))
        ctk.set_default_color_theme("blue")
        super().__init__()
        self.title(f"{APP_NAME} · {APP_VERSION}")
        self.geometry("1280x820")
        self.minsize(1080, 700)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.engine = QuizEngine()
        self.runtime = BundledCoreRuntime()
        self.client = SoopChatClient(self.engine, self._socket_status)
        self.overlay = OverlayServer(self.engine)
        self.overlay.start()

        self.quiz_sets = self._load_quiz_sets()
        self.active_set_name = next(iter(self.quiz_sets), "기본 퀴즈")
        self.engine.questions = self.quiz_sets[self.active_set_name]
        self.engine.ranking_mode = str(self.settings.get("ranking_mode", "correct_count"))
        self.engine.set_visual(
            theme=str(self.settings.get("overlay_theme", "dark")),
            motion=bool(self.settings.get("overlay_motion", True)),
            compact_ranking=bool(self.settings.get("compact_ranking", False)),
            show_fastest=bool(self.settings.get("show_fastest", True)),
        )

        self._page_name = "진행"
        self._runtime_error = ""
        self._build_shell()
        self.show_page("진행")
        self.after(120, self._refresh)
        self.runtime.start_async(lambda err: self.after(0, lambda: self._runtime_finished(err)))
        if not self.settings.get("onboarding_done"):
            self.after(700, self.show_onboarding)

    # ---------- storage ----------
    def _path(self, name: str) -> Path:
        return app_data_dir() / name

    def _load_json(self, name: str, default: Any) -> Any:
        try:
            return json.loads(self._path(name).read_text(encoding="utf-8"))
        except Exception:
            return default

    def _save_settings(self) -> None:
        try:
            self._path(SETTINGS_FILE).write_text(json.dumps(self.settings, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _sample_question(self) -> Question:
        return Question(kind="multiple", prompt="샘플 문제 · 2 + 2는?", choices=["3", "4", "5", "6"], answer="2", duration_sec=15)

    def _load_quiz_sets(self) -> dict[str, list[Question]]:
        raw = self._load_json(QUIZ_FILE, {})
        output: dict[str, list[Question]] = {}
        if isinstance(raw, dict):
            for name, rows in raw.items():
                if isinstance(rows, list):
                    parsed = [Question.from_dict(x) for x in rows if isinstance(x, dict)]
                    if parsed:
                        output[str(name)] = parsed
        if not output:
            output["기본 퀴즈"] = [self._sample_question()]
        return output

    def _save_quiz_sets(self) -> None:
        data = {name: [asdict(q) for q in rows] for name, rows in self.quiz_sets.items()}
        self._path(QUIZ_FILE).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- shell ----------
    def _build_shell(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.topbar = ctk.CTkFrame(self, corner_radius=0, height=62, fg_color=("#FFFFFF", "#101218"))
        self.topbar.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self.topbar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.topbar, text="SOOP QUIZ", font=(FONT, 19, "bold")).grid(row=0, column=0, padx=(22, 10), pady=16, sticky="w")
        self.top_status = ctk.CTkLabel(self.topbar, text="내부 엔진 준비 중", font=(FONT, 12, "bold"), text_color=("#596273", "#AEB7C8"))
        self.top_status.grid(row=0, column=1, padx=10, sticky="e")
        self.theme_menu = ctk.CTkOptionMenu(self.topbar, width=112, values=["다크", "라이트", "시스템"], command=self.change_appearance)
        self.theme_menu.set({"light": "라이트", "system": "시스템"}.get(str(self.settings.get("appearance", "dark")), "다크"))
        self.theme_menu.grid(row=0, column=2, padx=(8, 20), pady=12)

        self.sidebar = ctk.CTkFrame(self, width=188, corner_radius=0, fg_color=("#F4F6F9", "#151820"))
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        for i, name in enumerate(["진행", "문제 만들기", "방송 레이어", "설정"]):
            button = ctk.CTkButton(
                self.sidebar,
                text=name,
                height=44,
                anchor="w",
                corner_radius=10,
                fg_color="transparent",
                hover_color=("#E7ECF4", "#232936"),
                text_color=("#202633", "#E9EDF5"),
                font=(FONT, 13, "bold"),
                command=lambda n=name: self.show_page(n),
            )
            button.grid(row=i, column=0, padx=13, pady=(14 if i == 0 else 4, 0), sticky="ew")
            self.nav_buttons[name] = button
        self.sidebar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.sidebar, text=f"v{APP_VERSION}\n설치 없이 EXE 하나로 실행", justify="left", font=(FONT, 10), text_color=("#7B8494", "#7F899A")).grid(row=10, column=0, padx=18, pady=18, sticky="sw")
        self.sidebar.grid_rowconfigure(9, weight=1)

        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color=("#F8F9FB", "#0E1015"))
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

    def _clear_content(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()

    def show_page(self, name: str) -> None:
        self._page_name = name
        for nav_name, button in self.nav_buttons.items():
            if nav_name == name:
                button.configure(fg_color=("#DDE7FA", "#263554"), text_color=("#194C9E", "#D9E6FF"))
            else:
                button.configure(fg_color="transparent", text_color=("#202633", "#E9EDF5"))
        self._clear_content()
        if name == "진행":
            self._build_run_page()
        elif name == "문제 만들기":
            self._build_editor_page()
        elif name == "방송 레이어":
            self._build_overlay_page()
        else:
            self._build_settings_page()

    def _page_frame(self, title: str, subtitle: str) -> ctk.CTkFrame:
        outer = ctk.CTkFrame(self.content, fg_color="transparent")
        outer.grid(row=0, column=0, sticky="nsew", padx=28, pady=24)
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(outer, text=title, font=(FONT, 26, "bold"), anchor="w").grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(outer, text=subtitle, font=(FONT, 12), text_color=("#667085", "#929BAC"), anchor="w").grid(row=1, column=0, pady=(3, 18), sticky="ew")
        body = ctk.CTkFrame(outer, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew")
        return body

    # ---------- runtime / connection ----------
    def _runtime_finished(self, error: Optional[Exception]) -> None:
        if error:
            self._runtime_error = str(error)
            self.top_status.configure(text="내부 엔진 시작 실패", text_color="#E45462")
            messagebox.showerror("실행 준비 실패", f"방송 엔진을 시작하지 못했습니다.\n\n{error}\n\n프로그램을 다시 실행하거나 공식 배포본을 다시 받아주세요.")
        else:
            self._runtime_error = ""
            self.top_status.configure(text="내부 엔진 준비 완료", text_color="#36A66A")
        if self._page_name == "진행":
            self.show_page("진행")

    def _socket_status(self, text: str) -> None:
        try:
            self.after(0, lambda: self.top_status.configure(text=text))
        except Exception:
            pass

    def connect_broadcast(self) -> None:
        if not self.runtime.ready:
            messagebox.showwarning("준비 중", "내부 방송 엔진이 아직 준비 중입니다. 잠시 후 다시 눌러주세요.")
            return
        streamer_id = self.streamer_var.get().strip()
        if not streamer_id:
            messagebox.showwarning("방송 ID 필요", "SOOP 방송국 ID를 입력해주세요. 닉네임이 아니라 방송국 ID입니다.")
            return
        self.settings["streamer"] = streamer_id
        self._save_settings()
        try:
            self.client.connect(self.runtime.ws_url, streamer_id)
        except Exception as exc:
            messagebox.showerror("연결 실패", str(exc))

    def disconnect_broadcast(self) -> None:
        self.client.disconnect()

    # ---------- run page ----------
    def _build_run_page(self) -> None:
        body = self._page_frame("방송 진행", "방송 중에는 가운데 큰 버튼 하나만 따라가면 됩니다. 다음 단계로 자동으로 넘어가지 않습니다.")
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(1, weight=1)

        connect = ctk.CTkFrame(body, corner_radius=16)
        connect.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        connect.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(connect, text="방송 연결", font=(FONT, 14, "bold")).grid(row=0, column=0, padx=(18, 12), pady=16, sticky="w")
        self.streamer_var = ctk.StringVar(value=str(self.settings.get("streamer", "")))
        self.streamer_entry = ctk.CTkEntry(connect, textvariable=self.streamer_var, placeholder_text="SOOP 방송국 ID", height=38)
        self.streamer_entry.grid(row=0, column=1, padx=6, pady=12, sticky="ew")
        self.connect_button = ctk.CTkButton(connect, text="연결", width=100, height=38, command=self.connect_broadcast)
        self.connect_button.grid(row=0, column=2, padx=(8, 18), pady=12)

        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)
        quizbar = ctk.CTkFrame(left, corner_radius=16)
        quizbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        quizbar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(quizbar, text="퀴즈 세트", font=(FONT, 13, "bold")).grid(row=0, column=0, padx=(18, 10), pady=14)
        self.set_var = ctk.StringVar(value=self.active_set_name)
        self.set_menu = ctk.CTkOptionMenu(quizbar, values=list(self.quiz_sets), variable=self.set_var, command=self._change_active_set)
        self.set_menu.grid(row=0, column=1, padx=8, sticky="ew")
        ctk.CTkButton(quizbar, text="문제 편집", width=92, fg_color="transparent", border_width=1, text_color=("#2B3442", "#D9E0EA"), command=lambda: self.show_page("문제 만들기")).grid(row=0, column=2, padx=(8, 18), pady=11)

        stage = ctk.CTkFrame(left, corner_radius=18)
        stage.grid(row=1, column=0, sticky="nsew")
        stage.grid_columnconfigure(0, weight=1)
        self.stage_label = ctk.CTkLabel(stage, text="연결 대기", font=(FONT, 22, "bold"), anchor="w")
        self.stage_label.grid(row=0, column=0, padx=22, pady=(22, 4), sticky="ew")
        self.question_label = ctk.CTkLabel(stage, text="방송을 연결해주세요.", font=(FONT, 14), justify="left", anchor="w", wraplength=650)
        self.question_label.grid(row=1, column=0, padx=22, pady=(0, 14), sticky="ew")

        stats = ctk.CTkFrame(stage, fg_color="transparent")
        stats.grid(row=2, column=0, padx=18, sticky="ew")
        for i in range(3): stats.grid_columnconfigure(i, weight=1)
        self.stat_part = self._stat_card(stats, 0, "참가자")
        self.stat_ans = self._stat_card(stats, 1, "답변")
        self.stat_correct = self._stat_card(stats, 2, "정답")

        self.primary_button = ctk.CTkButton(stage, text="참가 모집 시작", height=62, corner_radius=14, font=(FONT, 16, "bold"), command=self.primary_action)
        self.primary_button.grid(row=3, column=0, padx=22, pady=(24, 10), sticky="ew")
        secondary = ctk.CTkFrame(stage, fg_color="transparent")
        secondary.grid(row=4, column=0, padx=22, pady=(0, 20), sticky="ew")
        secondary.grid_columnconfigure(2, weight=1)
        ctk.CTkButton(secondary, text="답변 강제 마감", width=120, fg_color="transparent", border_width=1, text_color=("#303846", "#D8DEE8"), command=lambda: self.engine.close_answers(False)).grid(row=0, column=0, padx=(0, 8))
        ctk.CTkButton(secondary, text="TOP10 미리보기", width=125, fg_color="transparent", border_width=1, text_color=("#303846", "#D8DEE8"), command=lambda: webbrowser.open(self.overlay.ranking_url)).grid(row=0, column=1)
        ctk.CTkButton(secondary, text="세션 초기화", width=100, fg_color="transparent", hover_color=("#FCE7EA", "#48262C"), text_color="#D04B59", command=self.reset_session).grid(row=0, column=3, sticky="e")

        right = ctk.CTkFrame(body, corner_radius=18)
        right.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(right, text="현재 TOP 10", font=(FONT, 17, "bold"), anchor="w").grid(row=0, column=0, padx=18, pady=(18, 3), sticky="ew")
        self.rank_mode = ctk.CTkSegmentedButton(right, values=["맞힌 개수", "점수", "연속 정답"], command=self._rank_mode_changed)
        self.rank_mode.grid(row=1, column=0, padx=16, pady=(8, 12), sticky="ew")
        self.rank_mode.set({"score": "점수", "streak": "연속 정답"}.get(self.engine.ranking_mode, "맞힌 개수"))
        self.rank_text = ctk.CTkTextbox(right, font=(FONT, 12), corner_radius=12, activate_scrollbars=True)
        self.rank_text.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self.rank_text.configure(state="disabled")

    def _stat_card(self, parent, column: int, title: str):
        card = ctk.CTkFrame(parent, corner_radius=12, fg_color=("#F2F4F7", "#191D25"))
        card.grid(row=0, column=column, padx=4, sticky="ew")
        value = ctk.CTkLabel(card, text="0", font=(FONT, 22, "bold"))
        value.pack(pady=(12, 0))
        ctk.CTkLabel(card, text=title, font=(FONT, 10), text_color=("#70798A", "#8993A4")).pack(pady=(0, 10))
        return value

    def _change_active_set(self, value: str) -> None:
        if value not in self.quiz_sets:
            return
        if self.engine.state not in {"READY", "DISCONNECTED", "FINISHED"}:
            messagebox.showwarning("진행 중", "퀴즈 진행 중에는 세트를 바꿀 수 없습니다. 세션을 마친 뒤 변경해주세요.")
            self.set_var.set(self.active_set_name)
            return
        self.active_set_name = value
        self.engine.questions = self.quiz_sets[value]
        self.engine.current_index = 0

    def _rank_mode_changed(self, value: str) -> None:
        self.engine.ranking_mode = "score" if value == "점수" else "streak" if value == "연속 정답" else "correct_count"
        self.settings["ranking_mode"] = self.engine.ranking_mode
        self._save_settings()

    def primary_action(self) -> None:
        state = self.engine.state
        ok = False
        if state == "READY": ok = self.engine.start_recruitment()
        elif state == "RECRUITING": ok = self.engine.close_recruitment()
        elif state == "LOCKED": ok = self.engine.show_question()
        elif state == "QUESTION_SHOWN": ok = self.engine.open_answers(self.client.current_seq)
        elif state == "ANSWERING": ok = self.engine.close_answers(False)
        elif state == "QUESTION_CLOSED": ok = self.engine.reveal_answer()
        elif state == "ANSWER_REVEALED": ok = self.engine.next_question()
        elif state == "FINISHED": ok = self.engine.start_recruitment()
        if not ok:
            self.bell()

    def reset_session(self) -> None:
        if messagebox.askyesno("세션 초기화", "참가자, 답변, 점수를 모두 지울까요?\n문제 세트는 삭제되지 않습니다."):
            self.engine.reset_session()

    # ---------- editor ----------
    def _build_editor_page(self) -> None:
        body = self._page_frame("문제 만들기", "객관식·주관식·OX·숫자형을 문제별로 섞어서 구성할 수 있습니다.")
        body.grid_columnconfigure(0, minsize=290)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, corner_radius=16)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(left, text="퀴즈 세트", font=(FONT, 14, "bold")).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")
        self.edit_set_var = ctk.StringVar(value=self.active_set_name)
        self.edit_set_menu = ctk.CTkOptionMenu(left, values=list(self.quiz_sets), variable=self.edit_set_var, command=self._editor_switch_set)
        self.edit_set_menu.grid(row=1, column=0, padx=14, sticky="ew")
        set_actions = ctk.CTkFrame(left, fg_color="transparent")
        set_actions.grid(row=2, column=0, padx=14, pady=8, sticky="ew")
        set_actions.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(set_actions, text="새 세트", height=32, command=self.new_quiz_set).grid(row=0, column=0, padx=(0, 4), sticky="ew")
        ctk.CTkButton(set_actions, text="세트 삭제", height=32, fg_color="transparent", border_width=1, text_color=("#323A48", "#D7DEE8"), command=self.delete_quiz_set).grid(row=0, column=1, padx=(4, 0), sticky="ew")
        self.question_list = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.question_list.grid(row=3, column=0, padx=10, pady=(4, 8), sticky="nsew")
        self.question_list.grid_columnconfigure(0, weight=1)
        bottom = ctk.CTkFrame(left, fg_color="transparent")
        bottom.grid(row=4, column=0, padx=14, pady=(0, 14), sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(bottom, text="+ 문제 추가", command=self.add_question).grid(row=0, column=0, padx=(0, 6), sticky="ew")
        ctk.CTkButton(bottom, text="↑", width=38, command=lambda: self.move_question(-1)).grid(row=0, column=1, padx=3)
        ctk.CTkButton(bottom, text="↓", width=38, command=lambda: self.move_question(1)).grid(row=0, column=2, padx=3)
        ctk.CTkButton(bottom, text="삭제", width=52, fg_color="transparent", border_width=1, text_color="#D04B59", command=self.delete_question).grid(row=0, column=3, padx=(6, 0))

        self.editor = ctk.CTkScrollableFrame(body, corner_radius=16)
        self.editor.grid(row=0, column=1, sticky="nsew")
        self.editor.grid_columnconfigure(1, weight=1)
        self._build_editor_form()
        self.selected_question_index = max(0, min(self.engine.current_index, len(self.engine.questions) - 1))
        self.refresh_question_list()
        self.load_question_form(self.selected_question_index)

    def _build_editor_form(self) -> None:
        row = 0
        ctk.CTkLabel(self.editor, text="문제 설정", font=(FONT, 18, "bold")).grid(row=row, column=0, columnspan=2, padx=20, pady=(20, 14), sticky="w"); row += 1
        self.kind_var = ctk.StringVar(value="객관식")
        self._field_label("문제 유형", row)
        ctk.CTkOptionMenu(self.editor, values=["객관식", "주관식", "OX", "숫자"], variable=self.kind_var, command=lambda _: self._update_editor_hint()).grid(row=row, column=1, padx=(8, 20), pady=6, sticky="ew"); row += 1
        self._field_label("문제", row)
        self.prompt_box = ctk.CTkTextbox(self.editor, height=100, font=(FONT, 13))
        self.prompt_box.grid(row=row, column=1, padx=(8, 20), pady=6, sticky="ew"); row += 1
        self._field_label("보기", row)
        self.choices_box = ctk.CTkTextbox(self.editor, height=116, font=(FONT, 12))
        self.choices_box.grid(row=row, column=1, padx=(8, 20), pady=6, sticky="ew"); row += 1
        self.editor_hint = ctk.CTkLabel(self.editor, text="보기는 한 줄에 하나씩 입력합니다.", anchor="w", font=(FONT, 10), text_color=("#6D7686", "#8D97A8"))
        self.editor_hint.grid(row=row, column=1, padx=(8, 20), sticky="ew"); row += 1
        self.answer_var = ctk.StringVar(); self._field_label("정답", row); ctk.CTkEntry(self.editor, textvariable=self.answer_var).grid(row=row, column=1, padx=(8, 20), pady=6, sticky="ew"); row += 1
        self.accepted_var = ctk.StringVar(); self._field_label("추가 인정 정답", row); ctk.CTkEntry(self.editor, textvariable=self.accepted_var, placeholder_text="주관식만 사용 · 쉼표로 구분").grid(row=row, column=1, padx=(8, 20), pady=6, sticky="ew"); row += 1

        divider = ctk.CTkFrame(self.editor, height=1, fg_color=("#DEE2E8", "#2B303A")); divider.grid(row=row, column=0, columnspan=2, padx=20, pady=14, sticky="ew"); row += 1
        self.duration_var = ctk.StringVar(value="15"); self._field_label("제한시간", row); ctk.CTkEntry(self.editor, textvariable=self.duration_var, placeholder_text="초").grid(row=row, column=1, padx=(8, 20), pady=6, sticky="ew"); row += 1
        self.policy_var = ctk.StringVar(value="마지막 답변 인정"); self._field_label("답변 변경", row); ctk.CTkOptionMenu(self.editor, values=["마지막 답변 인정", "첫 답변만 인정"], variable=self.policy_var).grid(row=row, column=1, padx=(8, 20), pady=6, sticky="ew"); row += 1
        self.scoring_var = ctk.StringVar(value="전체 정답자"); self._field_label("정답 처리", row); ctk.CTkOptionMenu(self.editor, values=["전체 정답자", "선착순 N명", "전체 + 선착순 보너스"], variable=self.scoring_var).grid(row=row, column=1, padx=(8, 20), pady=6, sticky="ew"); row += 1
        self.firstn_var = ctk.StringVar(value="3"); self._field_label("선착순 인원", row); ctk.CTkEntry(self.editor, textvariable=self.firstn_var, placeholder_text="예: 3").grid(row=row, column=1, padx=(8, 20), pady=6, sticky="ew"); row += 1
        self.basepoints_var = ctk.StringVar(value="100"); self._field_label("기본 점수", row); ctk.CTkEntry(self.editor, textvariable=self.basepoints_var).grid(row=row, column=1, padx=(8, 20), pady=6, sticky="ew"); row += 1
        self.rankpoints_var = ctk.StringVar(value="300,200,100"); self._field_label("1·2·3위 점수", row); ctk.CTkEntry(self.editor, textvariable=self.rankpoints_var, placeholder_text="300,200,100").grid(row=row, column=1, padx=(8, 20), pady=6, sticky="ew"); row += 1
        self.tolerance_var = ctk.StringVar(value="0"); self._field_label("숫자 허용 오차", row); ctk.CTkEntry(self.editor, textvariable=self.tolerance_var).grid(row=row, column=1, padx=(8, 20), pady=6, sticky="ew"); row += 1

        self.auto_time_var = ctk.BooleanVar(value=True)
        self.auto_quota_var = ctk.BooleanVar(value=False)
        self.ignore_space_var = ctk.BooleanVar(value=True)
        self.ignore_punct_var = ctk.BooleanVar(value=True)
        toggles = ctk.CTkFrame(self.editor, fg_color="transparent")
        toggles.grid(row=row, column=0, columnspan=2, padx=20, pady=(12, 4), sticky="ew")
        ctk.CTkSwitch(toggles, text="시간이 끝나면 답변만 마감", variable=self.auto_time_var, font=(FONT, 11)).pack(anchor="w", pady=4)
        ctk.CTkSwitch(toggles, text="선착순 N명 달성 시 답변만 마감", variable=self.auto_quota_var, font=(FONT, 11)).pack(anchor="w", pady=4)
        ctk.CTkSwitch(toggles, text="주관식 띄어쓰기 무시", variable=self.ignore_space_var, font=(FONT, 11)).pack(anchor="w", pady=4)
        ctk.CTkSwitch(toggles, text="주관식 특수문자 무시", variable=self.ignore_punct_var, font=(FONT, 11)).pack(anchor="w", pady=4)
        row += 1
        ctk.CTkButton(self.editor, text="문제 저장", height=48, font=(FONT, 14, "bold"), command=self.save_question).grid(row=row, column=0, columnspan=2, padx=20, pady=(16, 24), sticky="ew")

    def _field_label(self, text: str, row: int) -> None:
        ctk.CTkLabel(self.editor, text=text, font=(FONT, 11, "bold"), anchor="w").grid(row=row, column=0, padx=(20, 8), pady=6, sticky="nw")

    def _editor_switch_set(self, value: str) -> None:
        self.active_set_name = value
        self.engine.questions = self.quiz_sets[value]
        self.engine.current_index = 0
        self.selected_question_index = 0
        self.refresh_question_list()
        self.load_question_form(0)

    def refresh_question_list(self) -> None:
        if not hasattr(self, "question_list"):
            return
        for child in self.question_list.winfo_children(): child.destroy()
        labels = {"multiple": "객관식", "short": "주관식", "ox": "OX", "number": "숫자"}
        for i, q in enumerate(self.engine.questions):
            selected = i == getattr(self, "selected_question_index", 0)
            button = ctk.CTkButton(
                self.question_list,
                text=f"Q{i + 1} · {labels.get(q.kind, q.kind)}\n{q.prompt[:26] or '제목 없음'}",
                height=54,
                anchor="w",
                justify="left",
                fg_color=("#DCE8FB", "#273A5B") if selected else "transparent",
                hover_color=("#E8EDF5", "#242B36"),
                text_color=("#1E2A3C", "#E7ECF5"),
                command=lambda idx=i: self.load_question_form(idx),
            )
            button.grid(row=i, column=0, padx=4, pady=3, sticky="ew")

    def load_question_form(self, index: int) -> None:
        if not self.engine.questions:
            return
        index = max(0, min(index, len(self.engine.questions) - 1))
        self.selected_question_index = index
        q = self.engine.questions[index]
        self.kind_var.set({"multiple": "객관식", "short": "주관식", "ox": "OX", "number": "숫자"}.get(q.kind, "객관식"))
        self.prompt_box.delete("1.0", "end"); self.prompt_box.insert("1.0", q.prompt)
        self.choices_box.delete("1.0", "end"); self.choices_box.insert("1.0", "\n".join(q.choices))
        self.answer_var.set(q.answer)
        self.accepted_var.set(", ".join(q.accepted_answers))
        self.duration_var.set(str(q.duration_sec))
        self.policy_var.set("첫 답변만 인정" if q.answer_policy == "first" else "마지막 답변 인정")
        self.scoring_var.set("선착순 N명" if q.scoring_mode == "first_n" else "전체 + 선착순 보너스" if q.scoring_mode == "mixed" else "전체 정답자")
        self.firstn_var.set(str(q.first_n)); self.basepoints_var.set(str(q.base_points)); self.rankpoints_var.set(",".join(map(str, q.rank_points)))
        self.tolerance_var.set(str(q.number_tolerance)); self.auto_time_var.set(q.auto_close_time); self.auto_quota_var.set(q.auto_close_quota); self.ignore_space_var.set(q.ignore_space); self.ignore_punct_var.set(q.ignore_punct)
        self._update_editor_hint()
        self.refresh_question_list()

    def _update_editor_hint(self) -> None:
        text = {
            "객관식": "객관식 · 보기는 한 줄에 하나씩. 정답에는 번호만 입력하세요. 시청자는 !1, !2 …",
            "주관식": "주관식 · 정답과 추가 인정 답안을 설정하세요. 시청자는 !정답 서울",
            "OX": "OX · 정답에는 O 또는 X. 시청자는 !O / !X",
            "숫자": "숫자 · 정답 숫자와 허용 오차를 설정하세요. 시청자는 !숫자 2500 또는 !2500",
        }.get(self.kind_var.get(), "")
        self.editor_hint.configure(text=text)

    def save_question(self) -> None:
        if not self.engine.questions:
            return
        kind = {"객관식": "multiple", "주관식": "short", "OX": "ox", "숫자": "number"}[self.kind_var.get()]
        prompt = self.prompt_box.get("1.0", "end").strip()
        if not prompt:
            messagebox.showwarning("문제 필요", "문제 내용을 입력해주세요.")
            return
        choices = [x.strip() for x in self.choices_box.get("1.0", "end").splitlines() if x.strip()][:6]
        answer = self.answer_var.get().strip()
        if kind == "multiple":
            if len(choices) < 2:
                messagebox.showwarning("보기 필요", "객관식은 보기가 최소 2개 필요합니다."); return
            idx = safe_int(answer, 0)
            if idx < 1 or idx > len(choices):
                messagebox.showwarning("정답 확인", f"정답에는 1~{len(choices)} 중 하나를 입력해주세요."); return
        elif kind == "ox":
            answer = answer.upper()
            if answer not in {"O", "X"}:
                messagebox.showwarning("정답 확인", "OX 문제의 정답은 O 또는 X여야 합니다."); return
        elif not answer:
            messagebox.showwarning("정답 필요", "정답을 입력해주세요."); return
        first_n = max(1, min(1000, safe_int(self.firstn_var.get(), 3)))
        points = [safe_int(x.strip(), 0) for x in self.rankpoints_var.get().split(",") if x.strip()]
        while len(points) < first_n:
            points.append(max(0, safe_int(self.basepoints_var.get(), 100)))
        q = Question(
            kind=kind, prompt=prompt, choices=choices if kind == "multiple" else (["O", "X"] if kind == "ox" else []), answer=answer,
            accepted_answers=[x.strip() for x in self.accepted_var.get().split(",") if x.strip()][:50],
            duration_sec=max(1, min(3600, safe_int(self.duration_var.get(), 15))),
            scoring_mode="first_n" if self.scoring_var.get() == "선착순 N명" else "mixed" if self.scoring_var.get() == "전체 + 선착순 보너스" else "all",
            first_n=first_n, base_points=safe_int(self.basepoints_var.get(), 100), rank_points=points[:1000],
            answer_policy="first" if self.policy_var.get() == "첫 답변만 인정" else "last",
            auto_close_time=bool(self.auto_time_var.get()), auto_close_quota=bool(self.auto_quota_var.get()),
            ignore_space=bool(self.ignore_space_var.get()), ignore_punct=bool(self.ignore_punct_var.get()), ignore_case=True,
            number_tolerance=max(0.0, safe_float(self.tolerance_var.get(), 0.0)),
        )
        self.engine.questions[self.selected_question_index] = q
        self.quiz_sets[self.active_set_name] = self.engine.questions
        self._save_quiz_sets(); self.refresh_question_list()
        messagebox.showinfo("저장 완료", "문제가 저장되었습니다.")

    def new_quiz_set(self) -> None:
        dialog = ctk.CTkInputDialog(text="새 퀴즈 세트 이름", title="새 퀴즈 세트")
        name = (dialog.get_input() or "").strip()
        if not name: return
        if name in self.quiz_sets:
            messagebox.showwarning("중복", "같은 이름의 퀴즈 세트가 있습니다."); return
        self.quiz_sets[name] = [Question(prompt="새 문제")]
        self.active_set_name = name; self.engine.questions = self.quiz_sets[name]; self.engine.current_index = 0
        self._save_quiz_sets(); self.show_page("문제 만들기")

    def delete_quiz_set(self) -> None:
        if len(self.quiz_sets) <= 1:
            messagebox.showwarning("삭제 불가", "퀴즈 세트는 최소 하나가 필요합니다."); return
        if not messagebox.askyesno("세트 삭제", f"'{self.active_set_name}' 세트를 삭제할까요?"): return
        self.quiz_sets.pop(self.active_set_name, None); self.active_set_name = next(iter(self.quiz_sets)); self.engine.questions = self.quiz_sets[self.active_set_name]; self.engine.current_index = 0
        self._save_quiz_sets(); self.show_page("문제 만들기")

    def add_question(self) -> None:
        self.engine.questions.append(Question(prompt="새 문제")); self.quiz_sets[self.active_set_name] = self.engine.questions; self._save_quiz_sets(); self.selected_question_index = len(self.engine.questions) - 1; self.load_question_form(self.selected_question_index)

    def delete_question(self) -> None:
        if len(self.engine.questions) <= 1:
            messagebox.showwarning("삭제 불가", "문제는 최소 하나가 필요합니다."); return
        idx = self.selected_question_index
        if not messagebox.askyesno("문제 삭제", f"Q{idx + 1}을 삭제할까요?"): return
        self.engine.questions.pop(idx); self.selected_question_index = max(0, idx - 1); self.quiz_sets[self.active_set_name] = self.engine.questions; self._save_quiz_sets(); self.load_question_form(self.selected_question_index)

    def move_question(self, delta: int) -> None:
        idx = self.selected_question_index; target = idx + delta
        if target < 0 or target >= len(self.engine.questions): return
        self.engine.questions[idx], self.engine.questions[target] = self.engine.questions[target], self.engine.questions[idx]
        self.selected_question_index = target; self.quiz_sets[self.active_set_name] = self.engine.questions; self._save_quiz_sets(); self.load_question_form(target)

    # ---------- overlays ----------
    def _build_overlay_page(self) -> None:
        body = self._page_frame("방송 레이어", "프릭샷 브라우저 소스에는 아래 URL을 그대로 넣으면 됩니다. 프로그램을 켜면 자동으로 작동합니다.")
        body.grid_columnconfigure((0, 1), weight=1)
        quiz = self._overlay_card(body, 0, "메인 퀴즈 레이어", "문제 · 보기 · START · 마감 · 정답 공개", self.overlay.quiz_url)
        rank = self._overlay_card(body, 1, "TOP10 순위 레이어", "별도 URL · 방송 화면 원하는 위치에 독립 배치", self.overlay.ranking_url)

        settings = ctk.CTkFrame(body, corner_radius=16)
        settings.grid(row=1, column=0, columnspan=2, pady=(14, 0), sticky="ew")
        settings.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(settings, text="레이어 스타일", font=(FONT, 15, "bold")).grid(row=0, column=0, columnspan=2, padx=18, pady=(18, 12), sticky="w")
        ctk.CTkLabel(settings, text="테마", font=(FONT, 11, "bold")).grid(row=1, column=0, padx=18, pady=8, sticky="w")
        self.overlay_theme = ctk.CTkSegmentedButton(settings, values=["다크", "라이트"], command=self._overlay_theme_changed)
        self.overlay_theme.grid(row=1, column=1, padx=(8, 18), pady=8, sticky="ew"); self.overlay_theme.set("라이트" if self.engine.visual["theme"] == "light" else "다크")
        self.motion_var = ctk.BooleanVar(value=bool(self.engine.visual["motion"])); ctk.CTkSwitch(settings, text="방송 애니메이션 사용", variable=self.motion_var, command=self._visual_switches).grid(row=2, column=0, columnspan=2, padx=18, pady=8, sticky="w")
        self.fastest_var = ctk.BooleanVar(value=bool(self.engine.visual["showFastest"])); ctk.CTkSwitch(settings, text="정답 공개 때 빠른 정답 TOP3 표시", variable=self.fastest_var, command=self._visual_switches).grid(row=3, column=0, columnspan=2, padx=18, pady=8, sticky="w")
        self.compact_var = ctk.BooleanVar(value=bool(self.engine.visual["compactRanking"])); ctk.CTkSwitch(settings, text="TOP10 레이어 컴팩트 모드", variable=self.compact_var, command=self._visual_switches).grid(row=4, column=0, columnspan=2, padx=18, pady=(8, 18), sticky="w")

    def _overlay_card(self, parent, column: int, title: str, desc: str, url: str):
        card = ctk.CTkFrame(parent, corner_radius=16)
        card.grid(row=0, column=column, padx=(0, 7) if column == 0 else (7, 0), sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text=title, font=(FONT, 16, "bold"), anchor="w").grid(row=0, column=0, padx=18, pady=(18, 3), sticky="ew")
        ctk.CTkLabel(card, text=desc, font=(FONT, 10), text_color=("#6E7787", "#8D96A6"), anchor="w").grid(row=1, column=0, padx=18, sticky="ew")
        entry = ctk.CTkEntry(card, height=38); entry.grid(row=2, column=0, padx=18, pady=(15, 10), sticky="ew"); entry.insert(0, url); entry.configure(state="readonly")
        actions = ctk.CTkFrame(card, fg_color="transparent"); actions.grid(row=3, column=0, padx=18, pady=(0, 18), sticky="ew"); actions.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(actions, text="URL 복사", command=lambda u=url: self.copy_text(u)).grid(row=0, column=0, padx=(0, 4), sticky="ew")
        ctk.CTkButton(actions, text="미리보기", fg_color="transparent", border_width=1, text_color=("#303846", "#D8DEE8"), command=lambda u=url: webbrowser.open(u)).grid(row=0, column=1, padx=(4, 0), sticky="ew")
        return card

    def copy_text(self, text: str) -> None:
        self.clipboard_clear(); self.clipboard_append(text); self.update()
        self.top_status.configure(text="레이어 URL을 복사했습니다", text_color="#36A66A")

    def _overlay_theme_changed(self, value: str) -> None:
        theme = "light" if value == "라이트" else "dark"; self.engine.set_visual(theme=theme); self.settings["overlay_theme"] = theme; self._save_settings()

    def _visual_switches(self) -> None:
        self.engine.set_visual(motion=self.motion_var.get(), compact_ranking=self.compact_var.get(), show_fastest=self.fastest_var.get())
        self.settings.update({"overlay_motion": bool(self.motion_var.get()), "compact_ranking": bool(self.compact_var.get()), "show_fastest": bool(self.fastest_var.get())}); self._save_settings()

    # ---------- settings / onboarding ----------
    def _build_settings_page(self) -> None:
        body = self._page_frame("설정", "처음 쓰는 스트리머가 기술 지식 없이 사용할 수 있도록 내부 엔진은 프로그램이 자동으로 관리합니다.")
        body.grid_columnconfigure(0, weight=1)
        guide = ctk.CTkFrame(body, corner_radius=16); guide.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(guide, text="처음 사용 가이드", font=(FONT, 15, "bold")).pack(anchor="w", padx=18, pady=(18, 4))
        ctk.CTkLabel(guide, text="1. 방송 ID 입력 → 2. 연결 → 3. 프릭샷에 레이어 URL 등록 → 4. 참가 모집 시작\nNode.js, Python, npm, 명령 프롬프트 설치나 실행은 필요 없습니다.", justify="left", font=(FONT, 12), text_color=("#5F697A", "#A0A8B6")).pack(anchor="w", padx=18, pady=(2, 14))
        ctk.CTkButton(guide, text="가이드 다시 보기", width=150, command=self.show_onboarding).pack(anchor="w", padx=18, pady=(0, 18))
        diag = ctk.CTkFrame(body, corner_radius=16); diag.grid(row=1, column=0, pady=(14, 0), sticky="ew")
        ctk.CTkLabel(diag, text="진단", font=(FONT, 15, "bold")).pack(anchor="w", padx=18, pady=(18, 6))
        self.diag_label = ctk.CTkLabel(diag, text=f"내부 엔진: {self.runtime.status}\n레이어 서버: 127.0.0.1:{self.overlay.port}\n데이터 위치: {app_data_dir()}", justify="left", font=(FONT, 11), text_color=("#5F697A", "#A0A8B6"))
        self.diag_label.pack(anchor="w", padx=18, pady=(0, 18))

    def show_onboarding(self) -> None:
        win = ctk.CTkToplevel(self); win.title("SOOP Quiz 시작하기"); win.geometry("570x470"); win.resizable(False, False); win.transient(self); win.grab_set()
        ctk.CTkLabel(win, text="처음이어도 3단계면 끝", font=(FONT, 23, "bold")).pack(anchor="w", padx=28, pady=(28, 4))
        ctk.CTkLabel(win, text="개발 도구나 별도 프로그램을 설치할 필요가 없습니다.", font=(FONT, 11), text_color=("#687283", "#9BA4B3")).pack(anchor="w", padx=28, pady=(0, 20))
        steps = [
            ("1", "SOOP 방송국 ID 입력", "진행 화면에서 본인의 방송국 ID를 입력하고 연결을 누릅니다."),
            ("2", "프릭샷에 레이어 URL 등록", "방송 레이어 메뉴에서 메인 퀴즈와 TOP10 URL을 각각 브라우저 소스로 등록합니다."),
            ("3", "!참여 로 시작", "참가 모집을 누르면 시청자는 채팅에 !참여. 이후 문제 유형에 맞는 명령어로 답합니다."),
        ]
        for number, title, desc in steps:
            row = ctk.CTkFrame(win, corner_radius=13); row.pack(fill="x", padx=28, pady=6)
            ctk.CTkLabel(row, text=number, width=38, height=38, corner_radius=19, fg_color=("#DDE9FF", "#27416B"), text_color=("#225CB2", "#DDE9FF"), font=(FONT, 14, "bold")).pack(side="left", padx=12, pady=12)
            text = ctk.CTkFrame(row, fg_color="transparent"); text.pack(side="left", fill="both", expand=True, padx=(0, 12), pady=10)
            ctk.CTkLabel(text, text=title, font=(FONT, 12, "bold"), anchor="w").pack(fill="x")
            ctk.CTkLabel(text, text=desc, font=(FONT, 10), text_color=("#687283", "#9BA4B3"), justify="left", anchor="w", wraplength=420).pack(fill="x", pady=(2, 0))
        def done():
            self.settings["onboarding_done"] = True; self._save_settings(); win.destroy()
        ctk.CTkButton(win, text="시작하기", height=44, command=done).pack(fill="x", padx=28, pady=(18, 24))

    def change_appearance(self, value: str) -> None:
        mode = "light" if value == "라이트" else "system" if value == "시스템" else "dark"
        ctk.set_appearance_mode(mode.capitalize())
        self.settings["appearance"] = mode; self._save_settings()

    # ---------- refresh / close ----------
    @staticmethod
    def _stage_info(state: str) -> tuple[str, str]:
        return {
            "DISCONNECTED": ("연결 대기", "참가 모집 시작"),
            "READY": ("방송 연결 완료", "참가 모집 시작"),
            "RECRUITING": ("참가 모집 중", "참가 마감"),
            "LOCKED": ("문제 준비", "문제 공개"),
            "QUESTION_SHOWN": ("문제 공개 · 답변 대기", "정답 입력 START"),
            "ANSWERING": ("답변 접수 중", "답변 마감"),
            "QUESTION_CLOSED": ("답변 마감", "정답 공개"),
            "ANSWER_REVEALED": ("정답 공개", "다음 문제"),
            "FINISHED": ("퀴즈 종료", "새 참가 모집"),
        }.get(state, (state, "진행"))

    def _refresh(self) -> None:
        try:
            if self._page_name == "진행" and hasattr(self, "stage_label"):
                stage, action = self._stage_info(self.engine.state)
                self.stage_label.configure(text=stage)
                q = self.engine.current_question
                if q:
                    self.question_label.configure(text=f"Q{self.engine.current_index + 1} / {len(self.engine.questions)}   {q.prompt}")
                else:
                    self.question_label.configure(text="문제가 없습니다.")
                self.stat_part.configure(text=str(len(self.engine.participants)))
                self.stat_ans.configure(text=str(len(self.engine.answers)))
                self.stat_correct.configure(text=str(sum(1 for a in self.engine.answers.values() if a.correct)))
                enabled = self.runtime.ready and self.engine.state != "DISCONNECTED"
                self.primary_button.configure(text=action, state="normal" if enabled else "disabled")
                if self.engine.connected:
                    self.connect_button.configure(text="연결 해제", command=self.disconnect_broadcast, fg_color="#3E4756")
                    self.streamer_entry.configure(state="disabled")
                else:
                    self.connect_button.configure(text="연결", command=self.connect_broadcast, fg_color=["#3B8ED0", "#1F6AA5"], state="normal" if self.runtime.ready else "disabled")
                    self.streamer_entry.configure(state="normal")
                rows = self.engine.ranking(10)
                self.rank_text.configure(state="normal"); self.rank_text.delete("1.0", "end")
                for row in rows:
                    value = f"{row['score']:,}점" if self.engine.ranking_mode == "score" else f"{row['streak']}연속" if self.engine.ranking_mode == "streak" else f"{row['correct']}개"
                    self.rank_text.insert("end", f"{row['rank']:>2}. {row['display']}\n     {value}\n")
                if not rows: self.rank_text.insert("end", "아직 순위가 없습니다.\n정답 공개 후 TOP10이 갱신됩니다.")
                self.rank_text.configure(state="disabled")
            if self._page_name == "설정" and hasattr(self, "diag_label"):
                self.diag_label.configure(text=f"내부 엔진: {self.runtime.status}\n방송 채팅: {self.client.status}\n레이어 서버: 127.0.0.1:{self.overlay.port}\n데이터 위치: {app_data_dir()}")
            if self.engine.connected:
                self.top_status.configure(text=f"● {self.engine.streamer_id} 연결", text_color="#36A66A")
            elif self.runtime.ready and not self._runtime_error:
                self.top_status.configure(text="내부 엔진 준비 완료", text_color=("#596273", "#AEB7C8"))
        finally:
            self.after(180, self._refresh)

    def on_close(self) -> None:
        try: self.client.disconnect()
        except Exception: pass
        try: self.overlay.stop()
        except Exception: pass
        try: self.runtime.stop()
        except Exception: pass
        self.destroy()


def main() -> None:
    QuizApp().mainloop()


if __name__ == "__main__":
    main()
