from __future__ import annotations

import ctypes
import sys

import customtkinter as ctk

import app_v3 as ui3
import app_v31 as ui31
import app_v4 as ui4
import app_v5 as ui5
from app_v5 import QuizAppV5
from common import APP_NAME, SESSION_FILE, SETTINGS_FILE
from core_runtime import BundledCoreRuntime
from overlay_server_v6 import OverlayServerV6
from quiz_engine_v6 import QuizEngineV6, UI_VERSION
from soop_client_v5 import SoopChatClientV5


FONT = "Malgun Gothic"
BG = ("#F5F7FA", "#090C11")
PANEL = ("#FFFFFF", "#11161E")
PANEL_2 = ("#F1F4F8", "#171D27")
PANEL_3 = ("#E9EEF5", "#1D2531")
LINE = ("#DCE2EA", "#26303D")
TEXT = ("#151A22", "#F5F7FA")
MUTED = ("#687486", "#95A1B3")
ACCENT = "#4B72FF"
ACCENT_HOVER = "#3E63E7"
GOOD = "#2FAE78"
DANGER = "#E25565"
WARNING = "#D99A2B"
PURPLE = "#8067E8"


# Existing pages are deliberately reused for stability. Patch their runtime
# design tokens so editor/chat/settings inherit the same visual language.
for module in (ui3, ui31, ui4, ui5):
    for name, value in {
        "FONT": FONT,
        "BG": BG,
        "PANEL": PANEL,
        "PANEL_2": PANEL_2,
        "LINE": LINE,
        "TEXT": TEXT,
        "MUTED": MUTED,
        "ACCENT": ACCENT,
        "GOOD": GOOD,
        "DANGER": DANGER,
    }.items():
        if hasattr(module, name):
            setattr(module, name, value)


class QuizAppV6(QuizAppV5):
    """v0.6 controller design rebuild on top of the v0.5 stable engine."""

    def __init__(self) -> None:
        self._recovery_last_write = 0.0
        self._recovery_signature = None
        self.settings = self._load_json(SETTINGS_FILE, {})
        appearance = str(self.settings.get("appearance", "dark")).lower()
        ctk.set_appearance_mode({"light": "Light", "system": "System"}.get(appearance, "Dark"))
        ctk.set_default_color_theme("blue")
        ctk.CTk.__init__(self)
        self.title(f"{APP_NAME} · {UI_VERSION}")
        self.geometry("1500x940")
        self.minsize(1200, 780)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.engine = QuizEngineV6()
        self.runtime = BundledCoreRuntime()
        self.client = SoopChatClientV5(self.engine, self._socket_status)
        self.overlay = OverlayServerV6(self.engine)
        self.overlay.start()

        self.quiz_sets = self._load_quiz_sets()
        self.active_set_name = str(self.settings.get("active_set") or next(iter(self.quiz_sets)))
        if self.active_set_name not in self.quiz_sets:
            self.active_set_name = next(iter(self.quiz_sets))
        self.engine.set_questions(self.quiz_sets[self.active_set_name])
        self.engine.ranking_mode = str(self.settings.get("ranking_mode", "correct_count"))
        self.engine.set_allow_mid_join(bool(self.settings.get("allow_mid_join", False)))
        self.engine.set_visual(
            theme=str(self.settings.get("overlay_theme", "dark")),
            motion=bool(self.settings.get("overlay_motion", True)),
            compact_ranking=bool(self.settings.get("compact_ranking", False)),
            show_fastest=bool(self.settings.get("show_fastest", True)),
        )
        with self.engine.lock:
            self.engine.visual["style"] = str(self.settings.get("overlay_style", "clean"))
            self.engine.visual["accent"] = str(self.settings.get("overlay_accent", "#5b7cff"))

        self._runtime_error = ""
        self._active_page = "진행"
        self._pages: dict[str, ctk.CTkFrame] = {}
        self._last_ui_version = -1
        self._last_chat_version = -1
        self._last_diag = ""
        self._pending_recovery = self._load_json(SESSION_FILE, {})
        self._closing = False
        self._core_restart_pending = False
        self._watchdog_failures = 0
        self._build_shell()
        self.show_page("진행")
        self._bind_hotkeys()
        self.after(100, self._ui_tick)
        self.after(2500, self._watchdog_tick)
        self.after(10000, self._checkpoint_tick)
        self.runtime.start_async(lambda err: self.after(0, lambda: self._runtime_finished(err)))
        if not self.settings.get("onboarding_done"):
            self.after(500, self.show_onboarding)

    # ---------- shell ----------
    def _build_shell(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.topbar = ctk.CTkFrame(self, height=72, corner_radius=0, fg_color=PANEL, border_width=0)
        self.topbar.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self.topbar.grid_columnconfigure(1, weight=1)

        brand = ctk.CTkFrame(self.topbar, fg_color="transparent")
        brand.grid(row=0, column=0, padx=(24, 10), pady=11, sticky="w")
        mark = ctk.CTkFrame(brand, width=34, height=34, corner_radius=10, fg_color=ACCENT)
        mark.pack(side="left", padx=(0, 11)); mark.pack_propagate(False)
        ctk.CTkLabel(mark, text="Q", font=(FONT, 15, "bold"), text_color="#FFFFFF").place(relx=.5, rely=.5, anchor="center")
        name = ctk.CTkFrame(brand, fg_color="transparent"); name.pack(side="left")
        ctk.CTkLabel(name, text="SOOP QUIZ STUDIO", font=(FONT, 15, "bold"), text_color=TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(name, text=f"Broadcast controller  ·  v{UI_VERSION}", font=(FONT, 9), text_color=MUTED, anchor="w").pack(anchor="w", pady=(1, 0))

        self.top_status = ctk.CTkLabel(self.topbar, text="●  방송 엔진 준비 중", font=(FONT, 11, "bold"), text_color=MUTED)
        self.top_status.grid(row=0, column=1, padx=12, sticky="e")
        self.theme_button = ctk.CTkButton(
            self.topbar, text=self._theme_button_text(), width=88, height=34, corner_radius=10,
            fg_color=PANEL_2, hover_color=PANEL_3, border_width=1, border_color=LINE,
            text_color=TEXT, font=(FONT, 10, "bold"), command=self.toggle_appearance,
        )
        self.theme_button.grid(row=0, column=2, padx=(8, 22), pady=16)

        self.sidebar = ctk.CTkFrame(self, width=222, corner_radius=0, fg_color=("#EDF1F6", "#0E131A"))
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(9, weight=1)

        ctk.CTkLabel(self.sidebar, text="WORKSPACE", font=(FONT, 8, "bold"), text_color=MUTED, anchor="w").grid(row=0, column=0, padx=18, pady=(20, 8), sticky="ew")
        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        nav = [
            ("진행", "방송 진행", "LIVE"),
            ("문제", "문제 편집", "QUIZ"),
            ("채팅", "참가자 채팅", "CHAT"),
            ("레이어", "방송 레이어", "LAYER"),
            ("설정", "설정 · 진단", "SYSTEM"),
        ]
        for idx, (key, label, tag) in enumerate(nav, start=1):
            btn = ctk.CTkButton(
                self.sidebar, text=f"{label}\n{tag}", height=52, anchor="w", corner_radius=12,
                fg_color="transparent", hover_color=("#E1E7EF", "#1A222D"), text_color=TEXT,
                font=(FONT, 11, "bold"), command=lambda k=key: self.show_page(k),
            )
            btn.grid(row=idx, column=0, padx=12, pady=3, sticky="ew")
            self.nav_buttons[key] = btn

        status_box = ctk.CTkFrame(self.sidebar, corner_radius=16, fg_color=PANEL, border_width=1, border_color=LINE)
        status_box.grid(row=10, column=0, padx=12, pady=14, sticky="ew")
        ctk.CTkLabel(status_box, text="SESSION", font=(FONT, 8, "bold"), text_color=MUTED, anchor="w").pack(fill="x", padx=13, pady=(12, 2))
        self.side_mode = ctk.CTkLabel(status_box, text="대기 중", font=(FONT, 11, "bold"), text_color=MUTED, anchor="w")
        self.side_mode.pack(fill="x", padx=13)
        ctk.CTkLabel(status_box, text="EXE 단독 실행 · 로컬 처리", font=(FONT, 8), text_color=MUTED, anchor="w").pack(fill="x", padx=13, pady=(3, 12))

        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color=BG)
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

    def show_page(self, name: str) -> None:
        self._active_page = name
        for key, button in self.nav_buttons.items():
            selected = key == name
            button.configure(
                fg_color=("#DDE6FF", "#182441") if selected else "transparent",
                text_color=("#315BCB", "#E5EBFF") if selected else TEXT,
                border_width=1 if selected else 0,
                border_color=("#C9D7FF", "#2B4070") if selected else LINE,
            )
        for page in self._pages.values():
            page.grid_remove()
        if name not in self._pages:
            builders = {
                "진행": self._build_run_page,
                "문제": self._build_editor_page,
                "채팅": self._build_chat_page,
                "레이어": self._build_overlay_page,
                "설정": self._build_settings_page,
            }
            self._pages[name] = builders[name]()
        self._pages[name].grid(row=0, column=0, sticky="nsew")
        self._last_ui_version = -1
        if name == "채팅":
            self._render_chat_page(force=True)
        else:
            self._refresh_active_page(force=True)

    def _page(self, title: str, subtitle: str) -> tuple[ctk.CTkFrame, ctk.CTkFrame]:
        page = ctk.CTkFrame(self.content, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        head = ctk.CTkFrame(page, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=30, pady=(24, 14))
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(head, text="SOOP QUIZ STUDIO", font=(FONT, 8, "bold"), text_color=ACCENT, anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(head, text=title, font=(FONT, 25, "bold"), text_color=TEXT, anchor="w").grid(row=1, column=0, pady=(2, 0), sticky="w")
        ctk.CTkLabel(head, text=subtitle, font=(FONT, 10), text_color=MUTED, anchor="w").grid(row=2, column=0, pady=(2, 0), sticky="w")
        body = ctk.CTkFrame(page, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=30, pady=(0, 26))
        return page, body

    # ---------- broadcast console ----------
    def _build_run_page(self) -> ctk.CTkFrame:
        page, body = self._page("방송 진행", "진행자가 지금 해야 할 동작 하나만 크게 보여줍니다. 모든 단계 전환은 수동입니다.")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        command = ctk.CTkFrame(body, corner_radius=18, fg_color=PANEL, border_width=1, border_color=LINE)
        command.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        command.grid_columnconfigure(1, weight=1); command.grid_columnconfigure(5, weight=1)
        ctk.CTkLabel(command, text="방송", font=(FONT, 9, "bold"), text_color=MUTED).grid(row=0, column=0, padx=(16, 8), pady=12, sticky="w")
        self.streamer_var = ctk.StringVar(value=str(self.settings.get("streamer", "")))
        self.streamer_entry = ctk.CTkEntry(command, textvariable=self.streamer_var, height=38, corner_radius=10, placeholder_text="SOOP 방송국 ID", border_color=LINE, fg_color=PANEL_2)
        self.streamer_entry.grid(row=0, column=1, padx=5, pady=9, sticky="ew")
        self.connect_button = ctk.CTkButton(command, text="연결", width=88, height=38, corner_radius=10, fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self.connect_broadcast)
        self.connect_button.grid(row=0, column=2, padx=5, pady=9)
        self.practice_button = ctk.CTkButton(command, text="연습", width=76, height=38, corner_radius=10, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, command=self.toggle_practice)
        self.practice_button.grid(row=0, column=3, padx=(5, 14), pady=9)
        ctk.CTkFrame(command, width=1, height=28, fg_color=LINE).grid(row=0, column=4, padx=(2, 14))
        ctk.CTkLabel(command, text="퀴즈 세트", font=(FONT, 9, "bold"), text_color=MUTED).grid(row=0, column=5, padx=(0, 7), pady=12, sticky="e")
        self.run_set_var = ctk.StringVar(value=self.active_set_name)
        self.run_set_menu = ctk.CTkOptionMenu(command, variable=self.run_set_var, values=list(self.quiz_sets), height=38, corner_radius=10, command=self._change_active_set)
        self.run_set_menu.grid(row=0, column=6, padx=5, pady=9, sticky="ew")
        ctk.CTkButton(command, text="편집", width=66, height=38, corner_radius=10, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, command=lambda: self.show_page("문제")).grid(row=0, column=7, padx=(5, 16), pady=9)

        main = ctk.CTkFrame(body, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew")
        main.grid_columnconfigure(0, weight=7); main.grid_columnconfigure(1, weight=4)
        main.grid_rowconfigure(0, weight=1)

        self.stage_card = ctk.CTkFrame(main, corner_radius=22, fg_color=PANEL, border_width=1, border_color=LINE)
        self.stage_card.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self.stage_card.grid_columnconfigure(0, weight=1); self.stage_card.grid_rowconfigure(3, weight=1)
        top = ctk.CTkFrame(self.stage_card, fg_color="transparent")
        top.grid(row=0, column=0, padx=24, pady=(22, 0), sticky="ew"); top.grid_columnconfigure(1, weight=1)
        self.stage_state_chip = ctk.CTkLabel(top, text="OFFLINE", corner_radius=999, fg_color=PANEL_2, text_color=MUTED, font=(FONT, 8, "bold"), padx=10, pady=5)
        self.stage_state_chip.grid(row=0, column=0, sticky="w")
        self.stage_kicker = ctk.CTkLabel(top, text="READY", font=(FONT, 9, "bold"), text_color=ACCENT, anchor="e")
        self.stage_kicker.grid(row=0, column=1, sticky="e")
        self.stage_label = ctk.CTkLabel(self.stage_card, text="연결 대기", font=(FONT, 28, "bold"), text_color=TEXT, anchor="w")
        self.stage_label.grid(row=1, column=0, padx=24, pady=(12, 0), sticky="ew")
        self.action_hint = ctk.CTkLabel(self.stage_card, text="다음 단계가 여기에 표시됩니다", font=(FONT, 10, "bold"), text_color=MUTED, anchor="w")
        self.action_hint.grid(row=2, column=0, padx=24, pady=(4, 0), sticky="ew")
        self.question_label = ctk.CTkLabel(self.stage_card, text="SOOP 방송을 연결하거나 연습 모드를 켜주세요.", font=(FONT, 16), text_color=MUTED, justify="left", anchor="nw", wraplength=750)
        self.question_label.grid(row=3, column=0, padx=24, pady=(18, 16), sticky="nsew")
        self.integrity_banner = ctk.CTkLabel(self.stage_card, text="", corner_radius=10, fg_color=("#FFF0F2", "#3A1F26"), text_color=("#B73748", "#FF9EAA"), font=(FONT, 10, "bold"), anchor="w")
        self.integrity_banner.grid(row=4, column=0, padx=24, pady=(0, 10), sticky="ew"); self.integrity_banner.grid_remove()
        ctk.CTkLabel(self.stage_card, text="NEXT ACTION", font=(FONT, 8, "bold"), text_color=MUTED, anchor="w").grid(row=5, column=0, padx=24, pady=(4, 5), sticky="ew")
        self.primary_button = ctk.CTkButton(self.stage_card, text="참가 모집 시작", height=68, corner_radius=15, font=(FONT, 17, "bold"), fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self.primary_action)
        self.primary_button.grid(row=6, column=0, padx=24, pady=(0, 12), sticky="ew")
        tools = ctk.CTkFrame(self.stage_card, fg_color="transparent")
        tools.grid(row=7, column=0, padx=24, pady=(0, 22), sticky="ew")
        for i in range(4): tools.grid_columnconfigure(i, weight=1)
        self.force_close_btn = ctk.CTkButton(tools, text="답변 마감", height=34, corner_radius=9, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, command=lambda: self.engine.close_answers())
        self.force_close_btn.grid(row=0, column=0, padx=(0, 4), sticky="ew")
        self.retry_btn = ctk.CTkButton(tools, text="문제 재진행", height=34, corner_radius=9, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, command=self.retry_question)
        self.retry_btn.grid(row=0, column=1, padx=4, sticky="ew")
        ctk.CTkButton(tools, text="참가자 관리", height=34, corner_radius=9, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, command=self.open_participants).grid(row=0, column=2, padx=4, sticky="ew")
        ctk.CTkButton(tools, text="결과 CSV", height=34, corner_radius=9, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, command=self.export_results_csv).grid(row=0, column=3, padx=(4, 0), sticky="ew")

        right = ctk.CTkFrame(main, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(7, 0)); right.grid_columnconfigure(0, weight=1); right.grid_rowconfigure(2, weight=1)
        stats = ctk.CTkFrame(right, fg_color="transparent"); stats.grid(row=0, column=0, sticky="ew")
        for i in range(3): stats.grid_columnconfigure(i, weight=1)
        self.stat_part = self._stat_v6(stats, 0, "참가자")
        self.stat_ans = self._stat_v6(stats, 1, "답변")
        self.stat_correct = self._stat_v6(stats, 2, "정답")

        self.practice_tools = ctk.CTkFrame(right, corner_radius=16, fg_color=PANEL, border_width=1, border_color=LINE)
        self.practice_tools.grid(row=1, column=0, sticky="ew", pady=(10, 10)); self.practice_tools.grid_columnconfigure(0, weight=1); self.practice_tools.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.practice_tools, text="연습 도구", font=(FONT, 9, "bold"), text_color=MUTED, anchor="w").grid(row=0, column=0, columnspan=2, padx=13, pady=(10, 5), sticky="ew")
        self.practice_join_btn = ctk.CTkButton(self.practice_tools, text="테스트 참가자 +12", height=32, corner_radius=9, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, command=lambda: self.engine.simulate_join(12))
        self.practice_join_btn.grid(row=1, column=0, padx=(13, 4), pady=(0, 11), sticky="ew")
        self.practice_answer_btn = ctk.CTkButton(self.practice_tools, text="테스트 답변 생성", height=32, corner_radius=9, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, command=self.engine.simulate_answers)
        self.practice_answer_btn.grid(row=1, column=1, padx=(4, 13), pady=(0, 11), sticky="ew")

        tabs = ctk.CTkTabview(right, corner_radius=18, fg_color=PANEL, segmented_button_fg_color=PANEL_2, segmented_button_selected_color=ACCENT, segmented_button_selected_hover_color=ACCENT_HOVER)
        tabs.grid(row=2, column=0, sticky="nsew"); tabs.add("TOP 10"); tabs.add("답변 현황")
        self.rank_text = ctk.CTkTextbox(tabs.tab("TOP 10"), corner_radius=11, fg_color=PANEL_2, border_width=0, font=(FONT, 11), activate_scrollbars=True)
        self.rank_text.pack(fill="both", expand=True, padx=9, pady=9); self.rank_text.configure(state="disabled")
        self.answer_text = ctk.CTkTextbox(tabs.tab("답변 현황"), corner_radius=11, fg_color=PANEL_2, border_width=0, font=(FONT, 10), activate_scrollbars=True)
        self.answer_text.pack(fill="both", expand=True, padx=9, pady=9); self.answer_text.configure(state="disabled")

        health = ctk.CTkFrame(body, corner_radius=14, fg_color=PANEL, border_width=1, border_color=LINE)
        health.grid(row=2, column=0, sticky="ew", pady=(12, 0)); health.grid_columnconfigure(2, weight=1)
        self.run_ws_status = ctk.CTkLabel(health, text="● WebSocket 확인 중", font=(FONT, 9, "bold"), text_color=MUTED)
        self.run_ws_status.grid(row=0, column=0, padx=(13, 8), pady=9, sticky="w")
        self.pipeline_label = ctk.CTkLabel(health, text="수집 파이프라인 확인 중", font=(FONT, 9), text_color=MUTED)
        self.pipeline_label.grid(row=0, column=1, padx=8, pady=9, sticky="w")
        self.run_last_chat = ctk.CTkLabel(health, text="참가자 채팅: 아직 없음", font=(FONT, 9), text_color=MUTED, anchor="e")
        self.run_last_chat.grid(row=0, column=2, padx=(8, 13), pady=9, sticky="ew")

        ops = ctk.CTkFrame(body, fg_color="transparent")
        ops.grid(row=3, column=0, sticky="ew", pady=(9, 0)); ops.grid_columnconfigure(4, weight=1)
        ctk.CTkLabel(ops, text="운영 도구", font=(FONT, 8, "bold"), text_color=MUTED).grid(row=0, column=0, padx=(2, 8), pady=7)
        ctk.CTkButton(ops, text="문제 무효", width=84, height=31, corner_radius=9, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, command=self.void_question).grid(row=0, column=1, padx=4)
        ctk.CTkButton(ops, text="수동 판정", width=84, height=31, corner_radius=9, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, command=self.open_adjudication).grid(row=0, column=2, padx=4)
        ctk.CTkButton(ops, text="점수 · 탈락", width=96, height=31, corner_radius=9, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, command=self.open_participant_ops).grid(row=0, column=3, padx=4)
        ctk.CTkButton(ops, text="참가자 채팅 보기", width=120, height=31, corner_radius=9, fg_color="transparent", border_width=1, border_color=LINE, hover_color=PANEL_2, text_color=MUTED, command=lambda: self.show_page("채팅")).grid(row=0, column=5, padx=(8, 0), sticky="e")

        self.recovery_button = ctk.CTkButton(body, text="이전 세션을 복구할 수 있습니다", height=32, corner_radius=10, fg_color=PURPLE, hover_color="#6E56D0", command=self.restore_recovery)
        if isinstance(self._pending_recovery, dict) and self._pending_recovery.get("hadSession"):
            self.recovery_button.grid(row=4, column=0, sticky="ew", pady=(9, 0))
        return page

    def _stat_v6(self, parent: ctk.CTkFrame, col: int, label: str) -> ctk.CTkLabel:
        box = ctk.CTkFrame(parent, corner_radius=15, fg_color=PANEL, border_width=1, border_color=LINE)
        box.grid(row=0, column=col, padx=(0 if col == 0 else 4, 0 if col == 2 else 4), sticky="ew")
        ctk.CTkLabel(box, text=label.upper(), font=(FONT, 8, "bold"), text_color=MUTED).pack(anchor="w", padx=12, pady=(10, 0))
        value = ctk.CTkLabel(box, text="0", font=(FONT, 23, "bold"), text_color=TEXT)
        value.pack(anchor="w", padx=12, pady=(1, 9))
        return value

    def _render_run_state(self) -> None:
        super()._render_run_state()
        if not hasattr(self, "stage_state_chip"):
            return
        state = self.engine.state
        _kicker, _stage, action = self._stage_info(state)
        meta = {
            "DISCONNECTED": ("OFFLINE", MUTED),
            "READY": ("READY", GOOD),
            "RECRUITING": ("RECRUITING", ACCENT),
            "LOCKED": ("READY", ACCENT),
            "QUESTION_SHOWN": ("PREVIEW", WARNING),
            "ANSWERING": ("LIVE ANSWERS", GOOD),
            "QUESTION_CLOSED": ("CLOSED", WARNING),
            "ANSWER_REVEALED": ("RESULT", PURPLE),
            "QUESTION_VOID": ("VOID", DANGER),
            "FINISHED": ("FINAL", PURPLE),
        }.get(state, (state, MUTED))
        self.stage_state_chip.configure(text=meta[0], text_color=meta[1], fg_color=PANEL_2)
        self.stage_card.configure(border_color=meta[1] if state not in {"DISCONNECTED", "READY"} else LINE)
        self.action_hint.configure(text=f"다음 동작 · {action}")
        if state == "ANSWERING":
            self.primary_button.configure(fg_color=GOOD, hover_color="#268E64")
        elif state == "QUESTION_CLOSED":
            self.primary_button.configure(fg_color=PURPLE, hover_color="#6E56D0")
        elif state == "QUESTION_VOID":
            self.primary_button.configure(fg_color=DANGER, hover_color="#C94756")
        else:
            self.primary_button.configure(fg_color=ACCENT, hover_color=ACCENT_HOVER)

    def _render_diag(self) -> None:
        if not hasattr(self, "diag_label"):
            return
        d = self.client.diagnostics()
        age = "없음" if d.get("lastEventAgeSec") is None else f"{d['lastEventAgeSec']:.1f}초 전"
        text = (
            f"앱 버전: {UI_VERSION}\n"
            f"내부 엔진: {self.runtime.status}\n"
            f"WebSocket: {d.get('health')} · {d.get('status')}\n"
            f"프로토콜: {d.get('protocol') or '-'} · 구독: {'예' if d.get('subscribed') else '아니오'}\n"
            f"최근 이벤트: {age} · seq {d.get('lastEventSeq', 0):,}\n"
            f"수집 큐: {d.get('queueDepth', 0):,} · peak {d.get('queuePeak', 0):,} · drop {d.get('queueDrops', 0):,}\n"
            f"재연결: {d.get('reconnectCount', 0)} · gap: {d.get('gapCount', 0)} · resume 불가: {d.get('resumeUnavailableCount', 0)}\n"
            f"참가자 채팅: {self.engine.participant_chat_total:,}건 · 최근 500건 메모리 보관\n"
            f"레이어 서버: 127.0.0.1:{self.overlay.port}\n"
            f"현재 단계: {self.engine.state}"
        )
        if d.get("lastError"):
            text += f"\n최근 오류: {d['lastError']}"
        if text != self._last_diag:
            self.diag_label.configure(text=text)
            self._last_diag = text

    def show_onboarding(self) -> None:
        win = ctk.CTkToplevel(self)
        win.title("SOOP Quiz Studio 시작하기")
        win.geometry("720x510")
        win.configure(fg_color=BG)
        win.transient(self); win.grab_set(); win.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(win, text="SOOP Quiz Studio", font=(FONT, 25, "bold"), text_color=TEXT, anchor="w").grid(row=0, column=0, padx=30, pady=(28, 4), sticky="ew")
        ctk.CTkLabel(win, text="처음 한 번만 아래 순서대로 설정하면 방송 중에는 큰 버튼만 누르면 됩니다.", font=(FONT, 10), text_color=MUTED, anchor="w").grid(row=1, column=0, padx=30, pady=(0, 14), sticky="ew")
        steps = [
            ("01", "SOOP 방송 연결", "방송국 ID를 입력하고 연결합니다. 연결 전에는 연습 모드로 전체 흐름을 시험할 수 있습니다."),
            ("02", "퀴즈 준비", "문제 편집에서 객관식·OX·주관식·숫자형 문제와 선착순 규칙을 설정합니다."),
            ("03", "레이어 등록", "메인 퀴즈와 TOP10/TOP3 URL을 프릭샷 또는 OBS 브라우저 소스에 각각 등록합니다."),
            ("04", "방송 진행", "참가 모집 → 문제 공개 → START → 마감 → 정답 공개를 자동 넘김 없이 직접 진행합니다."),
        ]
        for i, (no, title, desc) in enumerate(steps, start=2):
            card = ctk.CTkFrame(win, corner_radius=14, fg_color=PANEL, border_width=1, border_color=LINE)
            card.grid(row=i, column=0, padx=30, pady=5, sticky="ew"); card.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(card, text=no, width=44, font=(FONT, 10, "bold"), text_color=ACCENT).grid(row=0, column=0, padx=(14, 6), pady=13)
            wrap = ctk.CTkFrame(card, fg_color="transparent"); wrap.grid(row=0, column=1, padx=(0, 14), pady=10, sticky="ew")
            ctk.CTkLabel(wrap, text=title, font=(FONT, 11, "bold"), text_color=TEXT, anchor="w").pack(fill="x")
            ctk.CTkLabel(wrap, text=desc, font=(FONT, 9), text_color=MUTED, justify="left", anchor="w", wraplength=580).pack(fill="x", pady=(2, 0))
        def done() -> None:
            self.settings["onboarding_done"] = True; self._save_settings(); win.destroy()
        ctk.CTkButton(win, text="시작하기", height=44, corner_radius=12, fg_color=ACCENT, hover_color=ACCENT_HOVER, font=(FONT, 12, "bold"), command=done).grid(row=6, column=0, padx=30, pady=(14, 26), sticky="ew")


def _single_instance() -> bool:
    if sys.platform != "win32":
        return True
    try:
        kernel = ctypes.windll.kernel32
        handle = kernel.CreateMutexW(None, False, "SOOPQuizOverlay-v0.6-single-instance")
        if not handle:
            return True
        return kernel.GetLastError() != 183
    except Exception:
        return True


def main() -> None:
    if not _single_instance():
        try:
            ctypes.windll.user32.MessageBoxW(0, "SOOP Quiz Studio가 이미 실행 중입니다.", "SOOP Quiz Studio", 0x40)
        except Exception:
            pass
        return
    QuizAppV6().mainloop()


if __name__ == "__main__":
    main()
