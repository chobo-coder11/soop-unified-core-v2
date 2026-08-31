from __future__ import annotations

import csv
import json
import os
import webbrowser
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

import customtkinter as ctk
from tkinter import filedialog, messagebox

from common import APP_NAME, APP_VERSION, QUIZ_FILE, SESSION_FILE, SETTINGS_FILE, Question, app_data_dir, safe_float, safe_int
from core_runtime import BundledCoreRuntime
from overlay_server_v3 import OverlayServerV3
from quiz_engine_v3 import QuizEngineV3
from soop_client_v3 import SoopChatClientV3


FONT = "Malgun Gothic"
BG = ("#F4F6FA", "#0B0E14")
PANEL = ("#FFFFFF", "#141923")
PANEL_2 = ("#F7F9FC", "#181E29")
LINE = ("#E3E7EE", "#272E3C")
TEXT = ("#171B24", "#F4F6FA")
MUTED = ("#6D7788", "#9CA7B8")
ACCENT = "#4F7DFF"
GOOD = "#32B87B"
DANGER = "#E25362"


class QuizAppV3(ctk.CTk):
    def __init__(self) -> None:
        self.settings = self._load_json(SETTINGS_FILE, {})
        appearance = str(self.settings.get("appearance", "dark")).lower()
        ctk.set_appearance_mode({"light": "Light", "system": "System"}.get(appearance, "Dark"))
        ctk.set_default_color_theme("blue")
        super().__init__()
        self.title(f"{APP_NAME} · {APP_VERSION}")
        self.geometry("1380x880")
        self.minsize(1120, 720)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.engine = QuizEngineV3()
        self.runtime = BundledCoreRuntime()
        self.client = SoopChatClientV3(self.engine, self._socket_status)
        self.overlay = OverlayServerV3(self.engine)
        self.overlay.start()

        self.quiz_sets = self._load_quiz_sets()
        self.active_set_name = str(self.settings.get("active_set") or next(iter(self.quiz_sets)))
        if self.active_set_name not in self.quiz_sets:
            self.active_set_name = next(iter(self.quiz_sets))
        self.engine.set_questions(self.quiz_sets[self.active_set_name])
        self.engine.ranking_mode = str(self.settings.get("ranking_mode", "correct_count"))
        self.engine.set_visual(
            theme=str(self.settings.get("overlay_theme", "dark")),
            motion=bool(self.settings.get("overlay_motion", True)),
            compact_ranking=bool(self.settings.get("compact_ranking", False)),
            show_fastest=bool(self.settings.get("show_fastest", True)),
        )

        self._runtime_error = ""
        self._active_page = "진행"
        self._pages: dict[str, ctk.CTkFrame] = {}
        self._last_ui_version = -1
        self._last_diag = ""
        self._pending_recovery = self._load_json(SESSION_FILE, {})
        self._build_shell()
        self.show_page("진행")
        self._bind_hotkeys()
        self.after(100, self._ui_tick)
        self.runtime.start_async(lambda err: self.after(0, lambda: self._runtime_finished(err)))
        if not self.settings.get("onboarding_done"):
            self.after(500, self.show_onboarding)

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

    def _save_recovery(self) -> None:
        if not bool(self.settings.get("auto_recovery", True)):
            return
        try:
            payload = self.engine.recovery_state()
            payload["activeSet"] = self.active_set_name
            self._path(SESSION_FILE).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ---------- shell ----------
    def _build_shell(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.topbar = ctk.CTkFrame(self, height=66, corner_radius=0, fg_color=PANEL)
        self.topbar.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self.topbar.grid_columnconfigure(1, weight=1)
        brand = ctk.CTkFrame(self.topbar, fg_color="transparent")
        brand.grid(row=0, column=0, padx=(22, 8), pady=10, sticky="w")
        ctk.CTkLabel(brand, text="SOOP QUIZ", font=(FONT, 18, "bold"), text_color=TEXT).pack(side="left")
        ctk.CTkLabel(brand, text=f"  v{APP_VERSION}", font=(FONT, 10, "bold"), text_color=MUTED).pack(side="left", pady=(4, 0))

        self.top_status = ctk.CTkLabel(self.topbar, text="●  내부 엔진 준비 중", font=(FONT, 12, "bold"), text_color=MUTED)
        self.top_status.grid(row=0, column=1, padx=12, sticky="e")
        self.theme_button = ctk.CTkButton(self.topbar, width=92, height=34, corner_radius=10, fg_color=PANEL_2, hover_color=LINE, text_color=TEXT, text=self._theme_button_text(), command=self.toggle_appearance)
        self.theme_button.grid(row=0, column=2, padx=(6, 20), pady=14)

        self.sidebar = ctk.CTkFrame(self, width=204, corner_radius=0, fg_color=("#EEF1F6", "#10141C"))
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(10, weight=1)

        ctk.CTkLabel(self.sidebar, text="BROADCAST CONSOLE", font=(FONT, 9, "bold"), text_color=MUTED, anchor="w").grid(row=0, column=0, padx=18, pady=(18, 8), sticky="ew")
        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        labels = [("진행", "방송 진행"), ("문제", "문제 편집"), ("레이어", "방송 레이어"), ("설정", "설정 · 진단")]
        for idx, (key, label) in enumerate(labels, start=1):
            btn = ctk.CTkButton(self.sidebar, text=label, height=44, anchor="w", corner_radius=11, fg_color="transparent", hover_color=("#E0E6F0", "#1D2430"), text_color=TEXT, font=(FONT, 12, "bold"), command=lambda k=key: self.show_page(k))
            btn.grid(row=idx, column=0, padx=12, pady=3, sticky="ew")
            self.nav_buttons[key] = btn

        status_box = ctk.CTkFrame(self.sidebar, corner_radius=14, fg_color=PANEL)
        status_box.grid(row=11, column=0, padx=12, pady=14, sticky="ew")
        self.side_mode = ctk.CTkLabel(status_box, text="대기 중", font=(FONT, 11, "bold"), text_color=MUTED, anchor="w")
        self.side_mode.pack(fill="x", padx=13, pady=(11, 2))
        ctk.CTkLabel(status_box, text="EXE 하나로 실행 · 별도 설치 없음", font=(FONT, 9), text_color=MUTED, anchor="w").pack(fill="x", padx=13, pady=(0, 11))

        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color=BG)
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

    def _theme_button_text(self) -> str:
        current = str(self.settings.get("appearance", "dark"))
        return "라이트" if current == "dark" else "다크"

    def toggle_appearance(self) -> None:
        current = str(self.settings.get("appearance", "dark"))
        new = "light" if current == "dark" else "dark"
        self.settings["appearance"] = new
        self._save_settings()
        ctk.set_appearance_mode(new.capitalize())
        self.theme_button.configure(text=self._theme_button_text())

    def show_page(self, name: str) -> None:
        self._active_page = name
        for key, button in self.nav_buttons.items():
            selected = key == name
            button.configure(
                fg_color=("#DDE6FA", "#202D48") if selected else "transparent",
                text_color=("#2456B6", "#DCE7FF") if selected else TEXT,
            )
        for page in self._pages.values():
            page.grid_remove()
        if name not in self._pages:
            builder = {"진행": self._build_run_page, "문제": self._build_editor_page, "레이어": self._build_overlay_page, "설정": self._build_settings_page}[name]
            self._pages[name] = builder()
        self._pages[name].grid(row=0, column=0, sticky="nsew")
        self._last_ui_version = -1
        self._refresh_active_page(force=True)

    def _page(self, title: str, subtitle: str) -> tuple[ctk.CTkFrame, ctk.CTkFrame]:
        page = ctk.CTkFrame(self.content, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        head = ctk.CTkFrame(page, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=26, pady=(22, 13))
        ctk.CTkLabel(head, text=title, font=(FONT, 25, "bold"), text_color=TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(head, text=subtitle, font=(FONT, 11), text_color=MUTED, anchor="w").pack(anchor="w", pady=(2, 0))
        body = ctk.CTkFrame(page, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=26, pady=(0, 24))
        return page, body

    # ---------- runtime / status ----------
    def _runtime_finished(self, error: Optional[Exception]) -> None:
        if error:
            self._runtime_error = str(error)
            self.top_status.configure(text="●  내부 엔진 시작 실패", text_color=DANGER)
        else:
            self._runtime_error = ""
            self.top_status.configure(text="●  방송 엔진 준비 완료", text_color=GOOD)
        self._refresh_active_page(force=True)

    def _socket_status(self, text: str) -> None:
        try:
            self.after(0, lambda: self._set_top_status(text))
        except Exception:
            pass

    def _set_top_status(self, text: str) -> None:
        color = GOOD if "연결됨" in text else DANGER if "오류" in text or "실패" in text else MUTED
        self.top_status.configure(text=f"●  {text}", text_color=color)

    # ---------- run page ----------
    def _build_run_page(self) -> ctk.CTkFrame:
        page, body = self._page("방송 진행", "방송 중에는 이 화면만 보면 됩니다. 단계는 자동으로 넘어가지 않습니다.")
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(1, weight=1)

        connect = ctk.CTkFrame(body, corner_radius=16, fg_color=PANEL, border_width=1, border_color=LINE)
        connect.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        connect.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(connect, text="방송 연결", font=(FONT, 12, "bold"), text_color=TEXT).grid(row=0, column=0, padx=(16, 10), pady=13)
        self.streamer_var = ctk.StringVar(value=str(self.settings.get("streamer", "")))
        self.streamer_entry = ctk.CTkEntry(connect, textvariable=self.streamer_var, height=38, corner_radius=10, placeholder_text="SOOP 방송국 ID", border_color=LINE)
        self.streamer_entry.grid(row=0, column=1, padx=6, pady=10, sticky="ew")
        self.connect_button = ctk.CTkButton(connect, text="연결", width=90, height=38, corner_radius=10, command=self.connect_broadcast)
        self.connect_button.grid(row=0, column=2, padx=(6, 5), pady=10)
        self.practice_button = ctk.CTkButton(connect, text="연습 모드", width=100, height=38, corner_radius=10, fg_color=PANEL_2, hover_color=LINE, text_color=TEXT, command=self.toggle_practice)
        self.practice_button.grid(row=0, column=3, padx=(5, 16), pady=10)

        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)

        setbar = ctk.CTkFrame(left, corner_radius=15, fg_color=PANEL, border_width=1, border_color=LINE)
        setbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        setbar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(setbar, text="퀴즈 세트", font=(FONT, 11, "bold"), text_color=MUTED).grid(row=0, column=0, padx=(15, 8), pady=12)
        self.run_set_var = ctk.StringVar(value=self.active_set_name)
        self.run_set_menu = ctk.CTkOptionMenu(setbar, variable=self.run_set_var, values=list(self.quiz_sets), height=34, command=self._change_active_set)
        self.run_set_menu.grid(row=0, column=1, padx=6, pady=9, sticky="ew")
        ctk.CTkButton(setbar, text="편집", width=68, height=34, corner_radius=9, fg_color=PANEL_2, hover_color=LINE, text_color=TEXT, command=lambda: self.show_page("문제")).grid(row=0, column=2, padx=(6, 14), pady=9)

        stage = ctk.CTkFrame(left, corner_radius=20, fg_color=PANEL, border_width=1, border_color=LINE)
        stage.grid(row=1, column=0, sticky="nsew")
        stage.grid_columnconfigure(0, weight=1)
        stage.grid_rowconfigure(2, weight=1)
        self.stage_kicker = ctk.CTkLabel(stage, text="READY", font=(FONT, 10, "bold"), text_color=ACCENT, anchor="w")
        self.stage_kicker.grid(row=0, column=0, padx=22, pady=(20, 3), sticky="ew")
        self.stage_label = ctk.CTkLabel(stage, text="연결 대기", font=(FONT, 23, "bold"), text_color=TEXT, anchor="w")
        self.stage_label.grid(row=1, column=0, padx=22, sticky="ew")
        self.question_label = ctk.CTkLabel(stage, text="SOOP 방송을 연결하거나 연습 모드를 켜주세요.", font=(FONT, 14), text_color=MUTED, justify="left", anchor="nw", wraplength=670)
        self.question_label.grid(row=2, column=0, padx=22, pady=(9, 12), sticky="nsew")

        self.integrity_banner = ctk.CTkLabel(stage, text="", height=0, corner_radius=10, fg_color=("#FCECEF", "#3A1E24"), text_color=("#B02D3D", "#FF9AA5"), font=(FONT, 10, "bold"), anchor="w")
        self.integrity_banner.grid(row=3, column=0, padx=22, pady=(0, 8), sticky="ew")
        self.integrity_banner.grid_remove()

        self.primary_button = ctk.CTkButton(stage, text="참가 모집 시작", height=62, corner_radius=14, font=(FONT, 16, "bold"), fg_color=ACCENT, hover_color="#3C68DD", command=self.primary_action)
        self.primary_button.grid(row=4, column=0, padx=22, pady=(8, 9), sticky="ew")

        tools = ctk.CTkFrame(stage, fg_color="transparent")
        tools.grid(row=5, column=0, padx=22, pady=(0, 19), sticky="ew")
        for i in range(4): tools.grid_columnconfigure(i, weight=1)
        self.force_close_btn = ctk.CTkButton(tools, text="답변 마감", height=34, corner_radius=9, fg_color=PANEL_2, hover_color=LINE, text_color=TEXT, command=lambda: self.engine.close_answers())
        self.force_close_btn.grid(row=0, column=0, padx=(0, 4), sticky="ew")
        self.retry_btn = ctk.CTkButton(tools, text="문제 재진행", height=34, corner_radius=9, fg_color=PANEL_2, hover_color=LINE, text_color=TEXT, command=self.retry_question)
        self.retry_btn.grid(row=0, column=1, padx=4, sticky="ew")
        ctk.CTkButton(tools, text="참가자 관리", height=34, corner_radius=9, fg_color=PANEL_2, hover_color=LINE, text_color=TEXT, command=self.open_participants).grid(row=0, column=2, padx=4, sticky="ew")
        ctk.CTkButton(tools, text="결과 CSV", height=34, corner_radius=9, fg_color=PANEL_2, hover_color=LINE, text_color=TEXT, command=self.export_results_csv).grid(row=0, column=3, padx=(4, 0), sticky="ew")

        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(2, weight=1)

        stats = ctk.CTkFrame(right, fg_color="transparent")
        stats.grid(row=0, column=0, sticky="ew")
        for i in range(3): stats.grid_columnconfigure(i, weight=1)
        self.stat_part = self._stat(stats, 0, "참가자")
        self.stat_ans = self._stat(stats, 1, "답변")
        self.stat_correct = self._stat(stats, 2, "정답")

        practice_tools = ctk.CTkFrame(right, corner_radius=14, fg_color=PANEL, border_width=1, border_color=LINE)
        practice_tools.grid(row=1, column=0, sticky="ew", pady=(10, 10))
        practice_tools.grid_columnconfigure(1, weight=1)
        self.practice_hint = ctk.CTkLabel(practice_tools, text="연습 모드에서 샘플 채팅을 즉시 만들어볼 수 있습니다.", font=(FONT, 10), text_color=MUTED, anchor="w")
        self.practice_hint.grid(row=0, column=0, columnspan=2, padx=13, pady=(10, 5), sticky="ew")
        self.practice_join_btn = ctk.CTkButton(practice_tools, text="테스트 참가자 +12", height=32, corner_radius=8, fg_color=PANEL_2, hover_color=LINE, text_color=TEXT, command=lambda: self.engine.simulate_join(12))
        self.practice_join_btn.grid(row=1, column=0, padx=(13, 4), pady=(0, 10), sticky="ew")
        self.practice_answer_btn = ctk.CTkButton(practice_tools, text="테스트 답변 생성", height=32, corner_radius=8, fg_color=PANEL_2, hover_color=LINE, text_color=TEXT, command=self.engine.simulate_answers)
        self.practice_answer_btn.grid(row=1, column=1, padx=(4, 13), pady=(0, 10), sticky="ew")

        tabs = ctk.CTkTabview(right, corner_radius=16, fg_color=PANEL, segmented_button_fg_color=PANEL_2, segmented_button_selected_color=ACCENT)
        tabs.grid(row=2, column=0, sticky="nsew")
        tabs.add("TOP 10")
        tabs.add("답변 현황")
        self.rank_text = ctk.CTkTextbox(tabs.tab("TOP 10"), corner_radius=10, fg_color=PANEL_2, border_width=0, font=(FONT, 12), activate_scrollbars=True)
        self.rank_text.pack(fill="both", expand=True, padx=9, pady=9)
        self.rank_text.configure(state="disabled")
        self.answer_text = ctk.CTkTextbox(tabs.tab("답변 현황"), corner_radius=10, fg_color=PANEL_2, border_width=0, font=(FONT, 11), activate_scrollbars=True)
        self.answer_text.pack(fill="both", expand=True, padx=9, pady=9)
        self.answer_text.configure(state="disabled")

        self.recovery_button = ctk.CTkButton(body, text="이전 세션 복구 가능", height=30, corner_radius=9, fg_color="#7A5AF8", hover_color="#6847DD", command=self.restore_recovery)
        if isinstance(self._pending_recovery, dict) and self._pending_recovery.get("hadSession"):
            self.recovery_button.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        return page

    def _stat(self, parent: ctk.CTkFrame, col: int, label: str) -> ctk.CTkLabel:
        box = ctk.CTkFrame(parent, corner_radius=14, fg_color=PANEL, border_width=1, border_color=LINE)
        box.grid(row=0, column=col, padx=(0 if col == 0 else 4, 0 if col == 2 else 4), sticky="ew")
        ctk.CTkLabel(box, text=label, font=(FONT, 9, "bold"), text_color=MUTED).pack(anchor="w", padx=12, pady=(10, 0))
        value = ctk.CTkLabel(box, text="0", font=(FONT, 22, "bold"), text_color=TEXT)
        value.pack(anchor="w", padx=12, pady=(0, 9))
        return value

    @staticmethod
    def _stage_info(state: str) -> tuple[str, str, str]:
        return {
            "DISCONNECTED": ("OFFLINE", "연결 대기", "참가 모집 시작"),
            "READY": ("READY", "방송 연결 완료", "참가 모집 시작"),
            "RECRUITING": ("RECRUITING", "참가 모집 중", "참가 마감"),
            "LOCKED": ("QUESTION", "문제 준비", "문제 공개"),
            "QUESTION_SHOWN": ("QUESTION OPEN", "문제 공개 · 답변 대기", "정답 입력 START"),
            "ANSWERING": ("LIVE", "답변 접수 중", "답변 마감"),
            "QUESTION_CLOSED": ("CLOSED", "답변 마감", "정답 공개"),
            "ANSWER_REVEALED": ("RESULT", "정답 공개", "다음 문제"),
            "FINISHED": ("FINAL", "퀴즈 종료", "새 참가 모집"),
        }.get(state, (state, state, "진행"))

    def connect_broadcast(self) -> None:
        if not self.runtime.ready:
            messagebox.showwarning("준비 중", "내부 방송 엔진이 아직 준비 중입니다.")
            return
        streamer = self.streamer_var.get().strip()
        if not streamer:
            messagebox.showwarning("방송 ID 필요", "SOOP 방송국 ID를 입력해주세요.")
            return
        if self.engine.practice_mode:
            self.engine.leave_practice()
        self.settings["streamer"] = streamer
        self._save_settings()
        self.client.connect(self.runtime.ws_url, streamer)

    def disconnect_broadcast(self) -> None:
        self.client.disconnect(wait=False)

    def toggle_practice(self) -> None:
        if self.engine.practice_mode:
            self.engine.leave_practice()
            return
        self.client.disconnect(wait=False)
        self.engine.enter_practice()

    def primary_action(self) -> None:
        state = self.engine.state
        if state in {"DISCONNECTED"}:
            return
        if state in {"READY", "FINISHED"}:
            self.engine.start_recruitment()
        elif state == "RECRUITING":
            self.engine.close_recruitment()
        elif state == "LOCKED":
            self.engine.show_question()
        elif state == "QUESTION_SHOWN":
            self.engine.open_answers(self.client.current_seq)
        elif state == "ANSWERING":
            self.engine.close_answers()
        elif state == "QUESTION_CLOSED":
            self.engine.reveal_answer()
        elif state == "ANSWER_REVEALED":
            self.engine.next_question()

    def retry_question(self) -> None:
        if not self.engine.retry_current_question():
            messagebox.showinfo("재진행 불가", "답변 마감 후 정답 공개 전에만 현재 문제를 재진행할 수 있습니다.")

    def _render_run_state(self) -> None:
        if not hasattr(self, "stage_label"):
            return
        state = self.engine.state
        kicker, stage, action = self._stage_info(state)
        self.stage_kicker.configure(text=kicker)
        self.stage_label.configure(text=stage)
        q = self.engine.current_question
        if q:
            prefix = f"Q{self.engine.current_index + 1} / {len(self.engine.questions)}"
            self.question_label.configure(text=f"{prefix}\n\n{q.prompt}")
        else:
            self.question_label.configure(text="문제가 없습니다. 문제 편집에서 문제를 추가해주세요.")
        self.stat_part.configure(text=f"{len(self.engine.participants):,}")
        self.stat_ans.configure(text=f"{len(self.engine.answers):,}")
        correct = sum(1 for a in self.engine.answers.values() if a.correct)
        self.stat_correct.configure(text=f"{correct:,}")
        enabled = self.engine.connected and state != "DISCONNECTED"
        self.primary_button.configure(text=action, state="normal" if enabled else "disabled")
        self.force_close_btn.configure(state="normal" if state == "ANSWERING" else "disabled")
        self.retry_btn.configure(state="normal" if state == "QUESTION_CLOSED" else "disabled")

        if self.engine.integrity_warning:
            self.integrity_banner.configure(text="  ⚠  " + self.engine.integrity_warning)
            self.integrity_banner.grid()
        else:
            self.integrity_banner.grid_remove()

        if self.engine.practice_mode:
            self.connect_button.configure(text="연결", state="disabled")
            self.streamer_entry.configure(state="disabled")
            self.practice_button.configure(text="연습 종료", fg_color="#7A5AF8", text_color="#FFFFFF")
            self.practice_join_btn.configure(state="normal")
            self.practice_answer_btn.configure(state="normal")
            self.side_mode.configure(text="연습 모드")
        elif self.engine.connected:
            self.connect_button.configure(text="연결 해제", state="normal", command=self.disconnect_broadcast, fg_color="#394354")
            self.streamer_entry.configure(state="disabled")
            self.practice_button.configure(text="연습 모드", fg_color=PANEL_2, text_color=TEXT)
            self.practice_join_btn.configure(state="disabled")
            self.practice_answer_btn.configure(state="disabled")
            self.side_mode.configure(text=f"LIVE · {self.engine.streamer_id}", text_color=GOOD)
        else:
            self.connect_button.configure(text="연결", command=self.connect_broadcast, state="normal" if self.runtime.ready else "disabled", fg_color=ACCENT)
            self.streamer_entry.configure(state="normal")
            self.practice_button.configure(text="연습 모드", state="normal", fg_color=PANEL_2, text_color=TEXT)
            self.practice_join_btn.configure(state="disabled")
            self.practice_answer_btn.configure(state="disabled")
            self.side_mode.configure(text="대기 중", text_color=MUTED)

        self._render_rank_text()
        self._render_answer_text()

    def _render_rank_text(self) -> None:
        rows = self.engine.ranking(10)
        self.rank_text.configure(state="normal")
        self.rank_text.delete("1.0", "end")
        if not rows:
            self.rank_text.insert("end", "아직 순위가 없습니다.\n정답 공개 후 TOP 10이 갱신됩니다.")
        for row in rows:
            if self.engine.ranking_mode == "score": value = f"{row['score']:,}점"
            elif self.engine.ranking_mode == "streak": value = f"최고 {row['streak']}연속"
            else: value = f"{row['correct']}개 정답"
            self.rank_text.insert("end", f"{row['rank']:>2}.  {row['display']}\n      {value}\n")
        self.rank_text.configure(state="disabled")

    def _render_answer_text(self) -> None:
        rows = self.engine.answer_feed(30)
        self.answer_text.configure(state="normal")
        self.answer_text.delete("1.0", "end")
        if not rows:
            self.answer_text.insert("end", "답변 접수 후 최근 답변이 여기에 표시됩니다.")
        for row in rows:
            mark = "✓" if row["correct"] else "·"
            rank = f" #{row['rank']}" if row["rank"] else ""
            self.answer_text.insert("end", f"{mark} {row['display']}  {row['answer']}{rank}\n")
        self.answer_text.configure(state="disabled")

    def open_participants(self) -> None:
        win = ctk.CTkToplevel(self)
        win.title("참가자 관리")
        win.geometry("620x600")
        win.transient(self)
        win.grab_set()
        win.grid_columnconfigure(0, weight=1)
        win.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(win, text=f"참가자 {len(self.engine.participants):,}명", font=(FONT, 20, "bold"), anchor="w").grid(row=0, column=0, padx=20, pady=(18, 8), sticky="ew")
        text = ctk.CTkTextbox(win, font=(FONT, 11))
        text.grid(row=1, column=0, padx=20, pady=8, sticky="nsew")
        for p in self.engine.participants.values():
            text.insert("end", f"{p.nickname}({p.user_id})  · 정답 {p.correct_count} · {p.score}점\n")
        text.configure(state="disabled")
        row = ctk.CTkFrame(win, fg_color="transparent")
        row.grid(row=2, column=0, padx=20, pady=(8, 18), sticky="ew")
        row.grid_columnconfigure(0, weight=1)
        uid = ctk.CTkEntry(row, placeholder_text="제외할 사용자 ID")
        uid.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        def remove() -> None:
            if self.engine.remove_participant(uid.get().strip()):
                win.destroy()
                self.open_participants()
            else:
                messagebox.showinfo("확인", "해당 ID의 참가자를 찾지 못했습니다.", parent=win)
        ctk.CTkButton(row, text="참가 제외", width=90, fg_color=DANGER, hover_color="#C94552", command=remove).grid(row=0, column=1)

    def export_results_csv(self) -> None:
        rows = self.engine.result_rows()
        if not rows:
            messagebox.showinfo("결과 없음", "내보낼 참가자 결과가 없습니다.")
            return
        path = filedialog.asksaveasfilename(title="퀴즈 결과 저장", defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="SOOP-Quiz-Result.csv")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["순위", "닉네임", "ID", "정답수", "점수", "최고연속", "평균정답시간(ms)"])
            for row in rows:
                writer.writerow([row["rank"], row["nickname"], row["userId"], row["correct"], row["score"], row["streak"], row["avgMs"] or ""])
        messagebox.showinfo("저장 완료", "퀴즈 결과 CSV를 저장했습니다.")

    def restore_recovery(self) -> None:
        if not self.engine.connected:
            messagebox.showinfo("먼저 연결", "방송 연결 또는 연습 모드를 먼저 켠 뒤 복구해주세요.")
            return
        payload = self._pending_recovery if isinstance(self._pending_recovery, dict) else {}
        active = str(payload.get("activeSet") or "")
        if active in self.quiz_sets and active != self.active_set_name:
            self._change_active_set(active)
        if self.engine.restore_recovery(payload):
            self.recovery_button.grid_remove()
            self._pending_recovery = {}
        else:
            messagebox.showinfo("복구 불가", "복구 가능한 이전 세션이 없습니다.")

    # ---------- editor ----------
    def _build_editor_page(self) -> ctk.CTkFrame:
        page, body = self._page("문제 편집", "방송 전에 문제를 빠르게 만들고 세트로 저장합니다.")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(body, corner_radius=15, fg_color=PANEL, border_width=1, border_color=LINE)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        toolbar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(toolbar, text="세트", font=(FONT, 10, "bold"), text_color=MUTED).grid(row=0, column=0, padx=(14, 6), pady=10)
        self.edit_set_var = ctk.StringVar(value=self.active_set_name)
        self.edit_set_menu = ctk.CTkOptionMenu(toolbar, variable=self.edit_set_var, values=list(self.quiz_sets), command=self._change_active_set)
        self.edit_set_menu.grid(row=0, column=1, padx=5, pady=9, sticky="ew")
        ctk.CTkButton(toolbar, text="새 세트", width=76, height=32, fg_color=PANEL_2, hover_color=LINE, text_color=TEXT, command=self.new_set).grid(row=0, column=2, padx=4)
        ctk.CTkButton(toolbar, text="JSON 가져오기", width=104, height=32, fg_color=PANEL_2, hover_color=LINE, text_color=TEXT, command=self.import_quiz_json).grid(row=0, column=3, padx=4)
        ctk.CTkButton(toolbar, text="JSON 내보내기", width=104, height=32, fg_color=PANEL_2, hover_color=LINE, text_color=TEXT, command=self.export_quiz_json).grid(row=0, column=4, padx=(4, 14))

        main = ctk.CTkFrame(body, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=3)
        main.grid_rowconfigure(0, weight=1)

        nav = ctk.CTkFrame(main, width=230, corner_radius=16, fg_color=PANEL, border_width=1, border_color=LINE)
        nav.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        nav.grid_propagate(False)
        nav.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(nav, text="문제 선택", font=(FONT, 12, "bold"), text_color=TEXT, anchor="w").grid(row=0, column=0, padx=14, pady=(15, 7), sticky="ew")
        self.question_index_var = ctk.StringVar(value="1")
        self.question_menu = ctk.CTkOptionMenu(nav, variable=self.question_index_var, values=["1"], command=lambda _: self._load_editor_question())
        self.question_menu.grid(row=1, column=0, padx=12, pady=5, sticky="ew")
        self.question_preview = ctk.CTkTextbox(nav, height=240, corner_radius=10, fg_color=PANEL_2, font=(FONT, 10))
        self.question_preview.grid(row=2, column=0, padx=12, pady=8, sticky="nsew")
        nav.grid_rowconfigure(2, weight=1)
        ctk.CTkButton(nav, text="+ 새 문제", height=36, command=self.add_question).grid(row=3, column=0, padx=12, pady=(5, 4), sticky="ew")
        ctk.CTkButton(nav, text="문제 복제", height=34, fg_color=PANEL_2, hover_color=LINE, text_color=TEXT, command=self.duplicate_question).grid(row=4, column=0, padx=12, pady=4, sticky="ew")
        ctk.CTkButton(nav, text="현재 문제 삭제", height=34, fg_color="transparent", border_width=1, border_color=("#E8B6BD", "#61313A"), text_color=DANGER, hover_color=("#FBEAEC", "#351D22"), command=self.delete_question).grid(row=5, column=0, padx=12, pady=(4, 12), sticky="ew")

        form = ctk.CTkScrollableFrame(main, corner_radius=16, fg_color=PANEL, border_width=1, border_color=LINE)
        form.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        form.grid_columnconfigure(1, weight=1)
        self.editor_vars: dict[str, Any] = {}
        row = 0
        row = self._field(form, row, "문제 유형", "kind", option=["객관식", "OX", "주관식", "숫자"])
        row = self._field(form, row, "문제", "prompt", multiline=True)
        row = self._field(form, row, "보기", "choices", multiline=True, hint="객관식일 때 한 줄에 보기 하나")
        row = self._field(form, row, "정답", "answer")
        row = self._field(form, row, "추가 정답", "accepted", hint="주관식 동의어를 쉼표로 구분")
        row = self._field(form, row, "제한 시간(초)", "duration")
        row = self._field(form, row, "점수 방식", "scoring", option=["전체 정답", "선착순", "전체 + 선착순 보너스"])
        row = self._field(form, row, "선착순 인원", "first_n")
        row = self._field(form, row, "기본 점수", "base_points")
        row = self._field(form, row, "선착순 점수", "rank_points", hint="예: 300,200,100")
        row = self._field(form, row, "답변 변경", "answer_policy", option=["마지막 답변 인정", "첫 답변 고정"])

        switch_box = ctk.CTkFrame(form, fg_color=PANEL_2, corner_radius=12)
        switch_box.grid(row=row, column=0, columnspan=2, padx=14, pady=9, sticky="ew")
        self.auto_time_var = ctk.BooleanVar(value=True)
        self.auto_quota_var = ctk.BooleanVar(value=False)
        self.ignore_space_var = ctk.BooleanVar(value=True)
        self.ignore_punct_var = ctk.BooleanVar(value=True)
        self.ignore_case_var = ctk.BooleanVar(value=True)
        for i, (text, var) in enumerate([
            ("시간 종료 시 답변만 자동 마감", self.auto_time_var),
            ("선착순 인원 달성 시 답변만 자동 마감", self.auto_quota_var),
            ("주관식 띄어쓰기 무시", self.ignore_space_var),
            ("주관식 문장부호 무시", self.ignore_punct_var),
            ("주관식 대소문자 무시", self.ignore_case_var),
        ]):
            ctk.CTkSwitch(switch_box, text=text, variable=var, font=(FONT, 10)).grid(row=i, column=0, padx=12, pady=6, sticky="w")
        row += 1
        save = ctk.CTkButton(form, text="현재 문제 저장", height=46, corner_radius=12, font=(FONT, 13, "bold"), command=self.save_current_question)
        save.grid(row=row, column=0, columnspan=2, padx=14, pady=(10, 18), sticky="ew")
        self._refresh_editor_navigation()
        self._load_editor_question()
        return page

    def _field(self, parent, row: int, label: str, key: str, *, multiline: bool = False, option: Optional[list[str]] = None, hint: str = "") -> int:
        ctk.CTkLabel(parent, text=label, font=(FONT, 10, "bold"), text_color=MUTED, anchor="w").grid(row=row, column=0, padx=(14, 10), pady=(8, 3), sticky="nw")
        if option:
            var = ctk.StringVar(value=option[0])
            widget = ctk.CTkOptionMenu(parent, values=option, variable=var, height=34)
            self.editor_vars[key] = var
        elif multiline:
            widget = ctk.CTkTextbox(parent, height=88 if key == "prompt" else 110, corner_radius=10, fg_color=PANEL_2, border_width=1, border_color=LINE, font=(FONT, 11))
            self.editor_vars[key] = widget
        else:
            var = ctk.StringVar()
            widget = ctk.CTkEntry(parent, textvariable=var, height=34, border_color=LINE)
            self.editor_vars[key] = var
        widget.grid(row=row, column=1, padx=(0, 14), pady=(7, 3), sticky="ew")
        if hint:
            ctk.CTkLabel(parent, text=hint, font=(FONT, 9), text_color=MUTED, anchor="w").grid(row=row + 1, column=1, padx=(2, 14), pady=(0, 4), sticky="ew")
            return row + 2
        return row + 1

    def _current_editor_index(self) -> int:
        return max(0, min(len(self.quiz_sets[self.active_set_name]) - 1, safe_int(self.question_index_var.get(), 1) - 1))

    def _refresh_editor_navigation(self) -> None:
        if not hasattr(self, "question_menu"):
            return
        rows = self.quiz_sets[self.active_set_name]
        values = [str(i + 1) for i in range(len(rows))]
        self.question_menu.configure(values=values)
        current = min(max(1, safe_int(self.question_index_var.get(), 1)), len(rows))
        self.question_index_var.set(str(current))
        self.question_preview.configure(state="normal")
        self.question_preview.delete("1.0", "end")
        for i, q in enumerate(rows, start=1):
            self.question_preview.insert("end", f"Q{i}. {q.prompt[:55]}\n\n")
        self.question_preview.configure(state="disabled")

    def _set_textbox(self, widget, value: str) -> None:
        widget.delete("1.0", "end"); widget.insert("1.0", value)

    def _load_editor_question(self) -> None:
        if not hasattr(self, "editor_vars"):
            return
        q = self.quiz_sets[self.active_set_name][self._current_editor_index()]
        kind_map = {"multiple": "객관식", "ox": "OX", "short": "주관식", "number": "숫자"}
        score_map = {"all": "전체 정답", "first_n": "선착순", "mixed": "전체 + 선착순 보너스"}
        policy_map = {"last": "마지막 답변 인정", "first": "첫 답변 고정"}
        self.editor_vars["kind"].set(kind_map.get(q.kind, "객관식"))
        self._set_textbox(self.editor_vars["prompt"], q.prompt)
        self._set_textbox(self.editor_vars["choices"], "\n".join(q.choices))
        self.editor_vars["answer"].set(str(q.answer))
        self.editor_vars["accepted"].set(", ".join(q.accepted_answers))
        self.editor_vars["duration"].set(str(q.duration_sec))
        self.editor_vars["scoring"].set(score_map.get(q.scoring_mode, "전체 정답"))
        self.editor_vars["first_n"].set(str(q.first_n))
        self.editor_vars["base_points"].set(str(q.base_points))
        self.editor_vars["rank_points"].set(",".join(str(x) for x in q.rank_points[:10]))
        self.editor_vars["answer_policy"].set(policy_map.get(q.answer_policy, "마지막 답변 인정"))
        self.auto_time_var.set(q.auto_close_time); self.auto_quota_var.set(q.auto_close_quota)
        self.ignore_space_var.set(q.ignore_space); self.ignore_punct_var.set(q.ignore_punct); self.ignore_case_var.set(q.ignore_case)

    def save_current_question(self) -> None:
        idx = self._current_editor_index()
        q = self.quiz_sets[self.active_set_name][idx]
        kind_rev = {"객관식": "multiple", "OX": "ox", "주관식": "short", "숫자": "number"}
        score_rev = {"전체 정답": "all", "선착순": "first_n", "전체 + 선착순 보너스": "mixed"}
        policy_rev = {"마지막 답변 인정": "last", "첫 답변 고정": "first"}
        q.kind = kind_rev.get(self.editor_vars["kind"].get(), "multiple")
        q.prompt = self.editor_vars["prompt"].get("1.0", "end").strip()
        q.choices = [x.strip() for x in self.editor_vars["choices"].get("1.0", "end").splitlines() if x.strip()][:6]
        if q.kind == "multiple" and len(q.choices) < 2:
            messagebox.showwarning("보기 필요", "객관식은 보기를 2개 이상 입력해주세요.")
            return
        q.answer = self.editor_vars["answer"].get().strip()
        q.accepted_answers = [x.strip() for x in self.editor_vars["accepted"].get().split(",") if x.strip()][:50]
        q.duration_sec = max(1, min(3600, safe_int(self.editor_vars["duration"].get(), 15)))
        q.scoring_mode = score_rev.get(self.editor_vars["scoring"].get(), "all")
        q.first_n = max(1, min(1000, safe_int(self.editor_vars["first_n"].get(), 3)))
        q.base_points = safe_int(self.editor_vars["base_points"].get(), 100)
        q.rank_points = [safe_int(x.strip(), 0) for x in self.editor_vars["rank_points"].get().split(",") if x.strip()][:1000]
        q.answer_policy = policy_rev.get(self.editor_vars["answer_policy"].get(), "last")
        q.auto_close_time = self.auto_time_var.get(); q.auto_close_quota = self.auto_quota_var.get()
        q.ignore_space = self.ignore_space_var.get(); q.ignore_punct = self.ignore_punct_var.get(); q.ignore_case = self.ignore_case_var.get()
        self._save_quiz_sets()
        self.engine.set_questions(self.quiz_sets[self.active_set_name])
        self._refresh_editor_navigation()
        messagebox.showinfo("저장 완료", "현재 문제를 저장했습니다.")

    def add_question(self) -> None:
        self.quiz_sets[self.active_set_name].append(Question(prompt="새 문제를 입력하세요"))
        self.question_index_var.set(str(len(self.quiz_sets[self.active_set_name])))
        self._save_quiz_sets(); self.engine.set_questions(self.quiz_sets[self.active_set_name])
        self._refresh_editor_navigation(); self._load_editor_question()

    def duplicate_question(self) -> None:
        q = Question.from_dict(asdict(self.quiz_sets[self.active_set_name][self._current_editor_index()]))
        self.quiz_sets[self.active_set_name].insert(self._current_editor_index() + 1, q)
        self.question_index_var.set(str(self._current_editor_index() + 2))
        self._save_quiz_sets(); self.engine.set_questions(self.quiz_sets[self.active_set_name])
        self._refresh_editor_navigation(); self._load_editor_question()

    def delete_question(self) -> None:
        rows = self.quiz_sets[self.active_set_name]
        if len(rows) <= 1:
            messagebox.showinfo("삭제 불가", "퀴즈 세트에는 최소 1개의 문제가 필요합니다.")
            return
        if not messagebox.askyesno("문제 삭제", "현재 문제를 삭제할까요?"):
            return
        rows.pop(self._current_editor_index())
        self.question_index_var.set("1")
        self._save_quiz_sets(); self.engine.set_questions(rows)
        self._refresh_editor_navigation(); self._load_editor_question()

    def new_set(self) -> None:
        dialog = ctk.CTkInputDialog(text="새 퀴즈 세트 이름", title="새 세트")
        name = (dialog.get_input() or "").strip()
        if not name or name in self.quiz_sets:
            return
        self.quiz_sets[name] = [Question(prompt="첫 문제를 입력하세요")]
        self._save_quiz_sets(); self._change_active_set(name)

    def import_quiz_json(self) -> None:
        path = filedialog.askopenfilename(title="퀴즈 JSON 가져오기", filetypes=[("JSON", "*.json")])
        if not path: return
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            if isinstance(raw, list):
                rows = [Question.from_dict(x) for x in raw if isinstance(x, dict)]
                if not rows: raise ValueError("문제가 없습니다")
                self.quiz_sets[self.active_set_name] = rows
            elif isinstance(raw, dict):
                parsed = {}
                for name, items in raw.items():
                    if isinstance(items, list):
                        rows = [Question.from_dict(x) for x in items if isinstance(x, dict)]
                        if rows: parsed[str(name)] = rows
                if not parsed: raise ValueError("올바른 퀴즈 세트가 없습니다")
                self.quiz_sets.update(parsed)
            else:
                raise ValueError("지원하지 않는 JSON 형식")
            self._save_quiz_sets(); self._sync_set_controls(); self._change_active_set(self.active_set_name)
            messagebox.showinfo("가져오기 완료", "퀴즈를 가져왔습니다.")
        except Exception as exc:
            messagebox.showerror("가져오기 실패", str(exc))

    def export_quiz_json(self) -> None:
        path = filedialog.asksaveasfilename(title="퀴즈 JSON 저장", defaultextension=".json", filetypes=[("JSON", "*.json")], initialfile=f"{self.active_set_name}.json")
        if not path: return
        rows = [asdict(q) for q in self.quiz_sets[self.active_set_name]]
        Path(path).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def _change_active_set(self, name: str) -> None:
        if name not in self.quiz_sets:
            return
        if self.engine.state not in {"DISCONNECTED", "READY", "FINISHED"}:
            messagebox.showwarning("진행 중", "퀴즈 진행 중에는 세트를 바꿀 수 없습니다.")
            self._sync_set_controls()
            return
        self.active_set_name = name
        self.settings["active_set"] = name
        self._save_settings()
        self.engine.set_questions(self.quiz_sets[name])
        self.engine.current_index = 0
        self._sync_set_controls()
        if hasattr(self, "question_index_var"):
            self.question_index_var.set("1"); self._refresh_editor_navigation(); self._load_editor_question()

    def _sync_set_controls(self) -> None:
        values = list(self.quiz_sets)
        if hasattr(self, "run_set_menu"):
            self.run_set_menu.configure(values=values); self.run_set_var.set(self.active_set_name)
        if hasattr(self, "edit_set_menu"):
            self.edit_set_menu.configure(values=values); self.edit_set_var.set(self.active_set_name)

    # ---------- overlay page ----------
    def _build_overlay_page(self) -> ctk.CTkFrame:
        page, body = self._page("방송 레이어", "프릭샷/OBS 브라우저 소스에 URL을 각각 넣으면 됩니다.")
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        self._overlay_card(body, 0, "메인 퀴즈", self.overlay.quiz_url, "문제 · START · 마감 · 정답 공개")
        self._overlay_card(body, 1, "TOP 10", self.overlay.rank_url, "별도 레이어로 독립 배치")

        settings = ctk.CTkFrame(body, corner_radius=16, fg_color=PANEL, border_width=1, border_color=LINE)
        settings.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        settings.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(settings, text="레이어 스타일", font=(FONT, 13, "bold"), text_color=TEXT).grid(row=0, column=0, padx=16, pady=(14, 9), sticky="w")
        self.overlay_theme_var = ctk.StringVar(value="라이트" if self.engine.visual["theme"] == "light" else "다크")
        theme = ctk.CTkSegmentedButton(settings, values=["다크", "라이트"], variable=self.overlay_theme_var, command=self._save_overlay_visual)
        theme.grid(row=0, column=1, padx=16, pady=(12, 7), sticky="e")
        self.motion_var = ctk.BooleanVar(value=bool(self.engine.visual["motion"]))
        self.fastest_var = ctk.BooleanVar(value=bool(self.engine.visual["showFastest"]))
        self.compact_var = ctk.BooleanVar(value=bool(self.engine.visual["compactRanking"]))
        ctk.CTkSwitch(settings, text="애니메이션", variable=self.motion_var, command=self._save_overlay_visual).grid(row=1, column=0, padx=16, pady=8, sticky="w")
        ctk.CTkSwitch(settings, text="정답 공개 시 선착순 3명", variable=self.fastest_var, command=self._save_overlay_visual).grid(row=1, column=1, padx=16, pady=8, sticky="w")
        ctk.CTkSwitch(settings, text="TOP10 컴팩트", variable=self.compact_var, command=self._save_overlay_visual).grid(row=2, column=0, padx=16, pady=(8, 15), sticky="w")
        return page

    def _overlay_card(self, parent, col: int, title: str, url: str, sub: str) -> None:
        card = ctk.CTkFrame(parent, corner_radius=16, fg_color=PANEL, border_width=1, border_color=LINE)
        card.grid(row=0, column=col, padx=(0 if col == 0 else 6, 6 if col == 0 else 0), sticky="nsew")
        ctk.CTkLabel(card, text=title, font=(FONT, 15, "bold"), text_color=TEXT, anchor="w").pack(fill="x", padx=16, pady=(15, 2))
        ctk.CTkLabel(card, text=sub, font=(FONT, 10), text_color=MUTED, anchor="w").pack(fill="x", padx=16)
        entry = ctk.CTkEntry(card, height=36, border_color=LINE)
        entry.pack(fill="x", padx=16, pady=(12, 7)); entry.insert(0, url); entry.configure(state="readonly")
        actions = ctk.CTkFrame(card, fg_color="transparent"); actions.pack(fill="x", padx=16, pady=(0, 14))
        ctk.CTkButton(actions, text="URL 복사", height=33, command=lambda u=url: self.copy_url(u)).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(actions, text="미리보기", height=33, fg_color=PANEL_2, hover_color=LINE, text_color=TEXT, command=lambda u=url: webbrowser.open(u)).pack(side="left", fill="x", expand=True, padx=(4, 0))

    def copy_url(self, url: str) -> None:
        self.clipboard_clear(); self.clipboard_append(url); self.update_idletasks()

    def _save_overlay_visual(self, *_args) -> None:
        theme = "light" if self.overlay_theme_var.get() == "라이트" else "dark"
        self.engine.set_visual(theme=theme, motion=self.motion_var.get(), compact_ranking=self.compact_var.get(), show_fastest=self.fastest_var.get())
        self.settings.update({"overlay_theme": theme, "overlay_motion": self.motion_var.get(), "compact_ranking": self.compact_var.get(), "show_fastest": self.fastest_var.get()})
        self._save_settings()

    # ---------- settings ----------
    def _build_settings_page(self) -> ctk.CTkFrame:
        page, body = self._page("설정 · 진단", "평소에는 건드릴 필요 없는 항목만 모았습니다.")
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        pref = ctk.CTkFrame(body, corner_radius=16, fg_color=PANEL, border_width=1, border_color=LINE)
        pref.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ctk.CTkLabel(pref, text="진행 설정", font=(FONT, 14, "bold"), text_color=TEXT).pack(anchor="w", padx=16, pady=(15, 8))
        self.rank_mode_var = ctk.StringVar(value={"score": "점수", "streak": "연속정답"}.get(self.engine.ranking_mode, "정답개수"))
        ctk.CTkLabel(pref, text="TOP10 기준", font=(FONT, 10, "bold"), text_color=MUTED).pack(anchor="w", padx=16)
        ctk.CTkSegmentedButton(pref, values=["정답개수", "점수", "연속정답"], variable=self.rank_mode_var, command=self.change_ranking_mode).pack(fill="x", padx=16, pady=(5, 12))
        self.hotkey_var = ctk.BooleanVar(value=bool(self.settings.get("hotkeys", True)))
        self.recovery_var = ctk.BooleanVar(value=bool(self.settings.get("auto_recovery", True)))
        ctk.CTkSwitch(pref, text="진행 단축키 사용 · Space / F8", variable=self.hotkey_var, command=self.save_basic_settings).pack(anchor="w", padx=16, pady=7)
        ctk.CTkSwitch(pref, text="세션 자동 복구 파일 저장", variable=self.recovery_var, command=self.save_basic_settings).pack(anchor="w", padx=16, pady=7)
        ctk.CTkButton(pref, text="세션 초기화", height=36, fg_color="transparent", border_width=1, border_color=("#E8B6BD", "#61313A"), text_color=DANGER, hover_color=("#FBEAEC", "#351D22"), command=self.reset_session_confirm).pack(fill="x", padx=16, pady=(13, 16))

        diag = ctk.CTkFrame(body, corner_radius=16, fg_color=PANEL, border_width=1, border_color=LINE)
        diag.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ctk.CTkLabel(diag, text="상태 진단", font=(FONT, 14, "bold"), text_color=TEXT).pack(anchor="w", padx=16, pady=(15, 8))
        self.diag_label = ctk.CTkLabel(diag, text="", font=(FONT, 10), text_color=MUTED, justify="left", anchor="nw", wraplength=500)
        self.diag_label.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        ctk.CTkButton(diag, text="데이터 폴더 열기", height=36, fg_color=PANEL_2, hover_color=LINE, text_color=TEXT, command=self.open_data_folder).pack(fill="x", padx=16, pady=(0, 16))
        return page

    def change_ranking_mode(self, value: str) -> None:
        mode = {"점수": "score", "연속정답": "streak"}.get(value, "correct_count")
        self.engine.ranking_mode = mode
        with self.engine.lock:
            self.engine._touch()
        self.settings["ranking_mode"] = mode; self._save_settings()

    def save_basic_settings(self) -> None:
        self.settings["hotkeys"] = self.hotkey_var.get(); self.settings["auto_recovery"] = self.recovery_var.get(); self._save_settings()

    def reset_session_confirm(self) -> None:
        if messagebox.askyesno("세션 초기화", "현재 참가자와 점수 기록을 모두 초기화할까요?"):
            self.engine.reset_session()
            try: self._path(SESSION_FILE).unlink(missing_ok=True)
            except Exception: pass

    def open_data_folder(self) -> None:
        try: os.startfile(str(app_data_dir()))
        except Exception: pass

    # ---------- hotkeys / refresh ----------
    def _bind_hotkeys(self) -> None:
        self.bind("<space>", self._hotkey_primary, add="+")
        self.bind("<F8>", self._hotkey_close, add="+")

    def _typing_focus(self) -> bool:
        widget = self.focus_get()
        if widget is None: return False
        cls = widget.winfo_class().lower()
        return any(x in cls for x in ("entry", "text"))

    def _hotkey_primary(self, _event=None):
        if not bool(self.settings.get("hotkeys", True)) or self._active_page != "진행" or self._typing_focus():
            return
        self.primary_action(); return "break"

    def _hotkey_close(self, _event=None):
        if not bool(self.settings.get("hotkeys", True)) or self._active_page != "진행" or self._typing_focus():
            return
        self.engine.close_answers(); return "break"

    def _refresh_active_page(self, force: bool = False) -> None:
        if self._active_page == "진행" and "진행" in self._pages:
            self._render_run_state()
        elif self._active_page == "설정" and "설정" in self._pages:
            self._render_diag()

    def _render_diag(self) -> None:
        if not hasattr(self, "diag_label"):
            return
        text = (
            f"앱 버전: {APP_VERSION}\n"
            f"내부 엔진: {self.runtime.status}\n"
            f"SOOP 채팅: {self.client.status}\n"
            f"레이어 서버: 127.0.0.1:{self.overlay.port}\n"
            f"상태 버전: {self.engine.state_version}\n"
            f"현재 단계: {self.engine.state}\n"
            f"마지막 채팅 seq: {self.engine.last_seq}\n"
            f"데이터 위치: {app_data_dir()}"
        )
        if text != self._last_diag:
            self.diag_label.configure(text=text); self._last_diag = text

    def _ui_tick(self) -> None:
        try:
            version = self.engine.state_version
            if version != self._last_ui_version:
                self._last_ui_version = version
                self._refresh_active_page()
                self._save_recovery()
            if self.engine.connected:
                if self.engine.practice_mode:
                    self.top_status.configure(text="●  연습 모드", text_color="#9B7CFF")
                else:
                    self.top_status.configure(text=f"●  {self.engine.streamer_id} 연결", text_color=GOOD)
            elif self.runtime.ready and not self._runtime_error and self.client.status == "연결 안 됨":
                self.top_status.configure(text="●  방송 엔진 준비 완료", text_color=MUTED)
            if self._active_page == "설정":
                self._render_diag()
        finally:
            self.after(180, self._ui_tick)

    # ---------- onboarding / shutdown ----------
    def show_onboarding(self) -> None:
        win = ctk.CTkToplevel(self)
        win.title("SOOP Quiz 시작하기")
        win.geometry("660x470")
        win.transient(self); win.grab_set()
        ctk.CTkLabel(win, text="방송에서 바로 쓰는 3단계", font=(FONT, 24, "bold")).pack(anchor="w", padx=28, pady=(26, 8))
        steps = [
            ("01", "방송 연결", "SOOP 방송국 ID를 입력하고 연결합니다. 처음 테스트할 때는 연습 모드를 써도 됩니다."),
            ("02", "문제 준비", "문제 편집에서 퀴즈를 만들고 방송 레이어 URL 2개를 프릭샷/OBS에 넣습니다."),
            ("03", "큰 버튼만 진행", "참가 모집 → 문제 공개 → START → 마감 → 정답 공개를 진행자가 직접 넘깁니다."),
        ]
        for no, title, desc in steps:
            card = ctk.CTkFrame(win, corner_radius=14, fg_color=PANEL_2)
            card.pack(fill="x", padx=28, pady=6)
            ctk.CTkLabel(card, text=no, width=48, font=(FONT, 12, "bold"), text_color=ACCENT).pack(side="left", padx=(14, 4), pady=14)
            wrap = ctk.CTkFrame(card, fg_color="transparent"); wrap.pack(side="left", fill="x", expand=True, pady=10)
            ctk.CTkLabel(wrap, text=title, font=(FONT, 12, "bold"), anchor="w").pack(fill="x")
            ctk.CTkLabel(wrap, text=desc, font=(FONT, 9), text_color=MUTED, justify="left", anchor="w", wraplength=500).pack(fill="x", pady=(2, 0))
        def done() -> None:
            self.settings["onboarding_done"] = True; self._save_settings(); win.destroy()
        ctk.CTkButton(win, text="시작하기", height=42, command=done).pack(fill="x", padx=28, pady=(14, 24))

    def on_close(self) -> None:
        self._save_recovery()
        try: self.client.disconnect(wait=False)
        except Exception: pass
        try: self.overlay.stop()
        except Exception: pass
        try: self.runtime.stop()
        except Exception: pass
        self.destroy()


def main() -> None:
    QuizAppV3().mainloop()


if __name__ == "__main__":
    main()
