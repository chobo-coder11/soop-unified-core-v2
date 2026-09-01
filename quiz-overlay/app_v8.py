from __future__ import annotations

import ctypes
import sys

import customtkinter as ctk
from tkinter import messagebox

import app_v3 as ui3
import app_v31 as ui31
import app_v4 as ui4
import app_v5 as ui5
import app_v6 as ui6
import app_v7 as ui7
from app_v6 import QuizAppV6
from app_v7 import QuizAppV7
from common import SESSION_FILE, SETTINGS_FILE
from core_runtime import BundledCoreRuntime
from overlay_server_v8 import OverlayServerV8
from quiz_engine_v8 import QuizEngineV8, UI_VERSION
from soop_client_v5 import SoopChatClientV5


PRODUCT_NAME = "SOOP Quiz Studio"
FONT = "Malgun Gothic"
BG = ("#F4F6F9", "#090C11")
SIDEBAR = ("#ECEFF4", "#0C1016")
PANEL = ("#FFFFFF", "#11161E")
PANEL_2 = ("#F3F5F8", "#171D26")
PANEL_3 = ("#E9EDF3", "#202733")
LINE = ("#D8DEE7", "#28313E")
TEXT = ("#171B23", "#F3F6FA")
MUTED = ("#6B7584", "#8E9AAA")
ACCENT = "#4F76F6"
ACCENT_HOVER = "#4267DD"
GOOD = "#31B77B"
DANGER = "#E25564"
WARNING = "#D9952B"
PURPLE = "#7562D8"
LIVE_RED = "#E9515F"


# Keep inherited editor/chat/layer/settings pages in the same visual system.
for module in (ui3, ui31, ui4, ui5, ui6, ui7):
    for name, value in {
        "FONT": FONT,
        "BG": BG,
        "PANEL": PANEL,
        "PANEL_2": PANEL_2,
        "PANEL_3": PANEL_3,
        "LINE": LINE,
        "TEXT": TEXT,
        "MUTED": MUTED,
        "ACCENT": ACCENT,
        "ACCENT_HOVER": ACCENT_HOVER,
        "GOOD": GOOD,
        "DANGER": DANGER,
        "WARNING": WARNING,
        "PURPLE": PURPLE,
        "LIVE_RED": LIVE_RED,
    }.items():
        if hasattr(module, name):
            setattr(module, name, value)


class QuizAppV8(QuizAppV7):
    """v0.8 controller rebuilt around glanceability instead of oversized widgets.

    Socket/scoring/session logic remains inherited. Only the product shell and
    broadcast control layout are rebuilt so a streamer can operate it quickly
    on a second monitor without clipped content or duplicated status controls.
    """

    def __init__(self) -> None:
        ctk.set_widget_scaling(1.0)
        self._recovery_last_write = 0.0
        self._recovery_signature = None
        self.settings = self._load_json(SETTINGS_FILE, {})
        appearance = str(self.settings.get("appearance", "dark")).lower()
        ctk.set_appearance_mode({"light": "Light", "system": "System"}.get(appearance, "Dark"))
        ctk.set_default_color_theme("blue")
        ctk.CTk.__init__(self)
        self.title(f"{PRODUCT_NAME} · v{UI_VERSION}")
        self.geometry("1480x900")
        self.minsize(1180, 720)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.engine = QuizEngineV8()
        self.runtime = BundledCoreRuntime()
        self.client = SoopChatClientV5(self.engine, self._socket_status)
        self.overlay = OverlayServerV8(self.engine)
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
        self.live_mode_var = ctk.BooleanVar(value=False)

        self._build_shell()
        self.show_page("진행")
        self._bind_hotkeys()
        self.bind("<F9>", lambda _e: self._toggle_live_mode_hotkey())
        self.after(100, self._ui_tick)
        self.after(2500, self._watchdog_tick)
        self.after(10000, self._checkpoint_tick)
        self.runtime.start_async(lambda err: self.after(0, lambda: self._runtime_finished(err)))
        if not self.settings.get("onboarding_done_v8"):
            self.after(450, self.show_onboarding)

    # ---------- shell ----------
    def _build_shell(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.topbar = ctk.CTkFrame(self, height=64, corner_radius=0, fg_color=PANEL)
        self.topbar.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self.topbar.grid_columnconfigure(1, weight=1)

        brand = ctk.CTkFrame(self.topbar, fg_color="transparent")
        brand.grid(row=0, column=0, padx=(18, 10), pady=10, sticky="w")
        mark = ctk.CTkFrame(brand, width=34, height=34, corner_radius=10, fg_color=ACCENT)
        mark.pack(side="left", padx=(0, 10)); mark.pack_propagate(False)
        ctk.CTkLabel(mark, text="Q", font=(FONT, 15, "bold"), text_color="#FFFFFF").place(relx=.5, rely=.5, anchor="center")
        name = ctk.CTkFrame(brand, fg_color="transparent"); name.pack(side="left")
        ctk.CTkLabel(name, text="SOOP QUIZ STUDIO", font=(FONT, 15, "bold"), text_color=TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(name, text=f"v{UI_VERSION}", font=(FONT, 9), text_color=MUTED, anchor="w").pack(anchor="w")

        self.top_status = ctk.CTkLabel(self.topbar, text="●  방송 엔진 준비 중", font=(FONT, 11, "bold"), text_color=MUTED)
        self.top_status.grid(row=0, column=1, padx=10, sticky="e")
        self.live_lock_button = ctk.CTkButton(
            self.topbar, text="방송 잠금", width=92, height=34, corner_radius=9,
            fg_color=PANEL_2, hover_color=PANEL_3, border_width=1, border_color=LINE,
            text_color=TEXT, font=(FONT, 10, "bold"), command=self._toggle_live_lock,
        )
        self.live_lock_button.grid(row=0, column=2, padx=(4, 6), pady=13)
        self.theme_button = ctk.CTkButton(
            self.topbar, text=self._theme_button_text(), width=74, height=34, corner_radius=9,
            fg_color="transparent", hover_color=PANEL_2, border_width=1, border_color=LINE,
            text_color=MUTED, font=(FONT, 10, "bold"), command=self.toggle_appearance,
        )
        self.theme_button.grid(row=0, column=3, padx=(0, 18), pady=13)

        self.sidebar = ctk.CTkFrame(self, width=190, corner_radius=0, fg_color=SIDEBAR)
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(7, weight=1)
        ctk.CTkLabel(self.sidebar, text="방송 도구", font=(FONT, 10, "bold"), text_color=MUTED, anchor="w").grid(row=0, column=0, padx=16, pady=(18, 8), sticky="ew")

        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        nav = [("진행", "방송 진행"), ("문제", "문제 편집"), ("채팅", "참가자 채팅"), ("레이어", "방송 레이어"), ("설정", "설정 · 진단")]
        for idx, (key, label) in enumerate(nav, start=1):
            btn = ctk.CTkButton(
                self.sidebar, text=label, height=44, anchor="w", corner_radius=10,
                fg_color="transparent", hover_color=("#E1E5EB", "#171D25"), text_color=TEXT,
                font=(FONT, 12, "bold"), command=lambda k=key: self.show_page(k),
            )
            btn.grid(row=idx, column=0, padx=10, pady=3, sticky="ew")
            self.nav_buttons[key] = btn

        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.grid(row=8, column=0, padx=16, pady=16, sticky="sew")
        self.side_mode = ctk.CTkLabel(footer, text="대기 중", font=(FONT, 11, "bold"), text_color=MUTED, anchor="w")
        self.side_mode.pack(fill="x")
        self.side_help = ctk.CTkLabel(footer, text="Space  다음 단계   ·   F9  방송 잠금", font=(FONT, 8), text_color=MUTED, anchor="w")
        self.side_help.pack(fill="x", pady=(3, 0))

        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color=BG)
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

    def show_page(self, name: str) -> None:
        if bool(self.live_mode_var.get()) and name in {"문제", "설정"}:
            self._flash_top("방송 잠금 중에는 문제 편집과 설정을 열 수 없습니다.", WARNING)
            return
        self._active_page = name
        for key, button in self.nav_buttons.items():
            selected = key == name
            button.configure(
                fg_color=("#DDE5F8", "#18233A") if selected else "transparent",
                text_color=("#3159B8", "#E7ECF7") if selected else TEXT,
                border_width=0,
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
        head.grid(row=0, column=0, sticky="ew", padx=24, pady=(16, 10))
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(head, text=title, font=(FONT, 24, "bold"), text_color=TEXT, anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(head, text=subtitle, font=(FONT, 10), text_color=MUTED, anchor="e").grid(row=0, column=1, padx=(18, 0), sticky="e")
        body = ctk.CTkFrame(page, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 18))
        return page, body

    # ---------- broadcast controller ----------
    def _build_run_page(self) -> ctk.CTkFrame:
        page, body = self._page("방송 진행", "현재 문제와 다음 행동만 보고 진행하세요")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        self.command_bar = ctk.CTkFrame(body, height=58, corner_radius=14, fg_color=PANEL, border_width=1, border_color=LINE)
        self.command_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.command_bar.grid_columnconfigure(1, weight=2)
        self.command_bar.grid_columnconfigure(6, weight=1)
        ctk.CTkLabel(self.command_bar, text="방송", font=(FONT, 10, "bold"), text_color=MUTED).grid(row=0, column=0, padx=(14, 7), pady=10)
        self.streamer_var = ctk.StringVar(value=str(self.settings.get("streamer", "")))
        self.streamer_entry = ctk.CTkEntry(
            self.command_bar, textvariable=self.streamer_var, height=36, corner_radius=9,
            placeholder_text="SOOP 방송국 ID", border_color=LINE, fg_color=PANEL_2, font=(FONT, 11),
        )
        self.streamer_entry.grid(row=0, column=1, padx=4, pady=10, sticky="ew")
        self.connect_button = ctk.CTkButton(
            self.command_bar, text="연결", width=78, height=36, corner_radius=9,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, font=(FONT, 11, "bold"), command=self.connect_broadcast,
        )
        self.connect_button.grid(row=0, column=2, padx=4, pady=10)
        self.practice_button = ctk.CTkButton(
            self.command_bar, text="연습", width=68, height=36, corner_radius=9,
            fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, font=(FONT, 10, "bold"), command=self.toggle_practice,
        )
        self.practice_button.grid(row=0, column=3, padx=(4, 12), pady=10)
        ctk.CTkFrame(self.command_bar, width=1, height=24, fg_color=LINE).grid(row=0, column=4, padx=(0, 12))
        ctk.CTkLabel(self.command_bar, text="퀴즈", font=(FONT, 10, "bold"), text_color=MUTED).grid(row=0, column=5, padx=(0, 7), pady=10, sticky="e")
        self.run_set_var = ctk.StringVar(value=self.active_set_name)
        self.run_set_menu = ctk.CTkOptionMenu(
            self.command_bar, variable=self.run_set_var, values=list(self.quiz_sets), height=36,
            corner_radius=9, font=(FONT, 10, "bold"), command=self._change_active_set,
        )
        self.run_set_menu.grid(row=0, column=6, padx=4, pady=10, sticky="ew")
        self.edit_quiz_button = ctk.CTkButton(
            self.command_bar, text="편집", width=64, height=36, corner_radius=9,
            fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, font=(FONT, 10, "bold"),
            command=lambda: self.show_page("문제"),
        )
        self.edit_quiz_button.grid(row=0, column=7, padx=(4, 14), pady=10)

        main = ctk.CTkFrame(body, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew")
        main.grid_columnconfigure(0, weight=7)
        main.grid_columnconfigure(1, weight=4)
        main.grid_rowconfigure(0, weight=1)

        self.stage_card = ctk.CTkFrame(main, corner_radius=18, fg_color=PANEL, border_width=1, border_color=LINE)
        self.stage_card.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.stage_card.grid_columnconfigure(0, weight=1)
        self.stage_card.grid_rowconfigure(3, weight=1)

        stage_head = ctk.CTkFrame(self.stage_card, fg_color="transparent")
        stage_head.grid(row=0, column=0, padx=22, pady=(18, 0), sticky="ew")
        stage_head.grid_columnconfigure(1, weight=1)
        self.stage_state_chip = ctk.CTkLabel(
            stage_head, text="OFFLINE", height=26, corner_radius=8, fg_color=PANEL_2,
            text_color=MUTED, font=(FONT, 9, "bold"), padx=9,
        )
        self.stage_state_chip.grid(row=0, column=0, sticky="w")
        self.question_meta = ctk.CTkLabel(stage_head, text="기본 퀴즈", font=(FONT, 10, "bold"), text_color=MUTED, anchor="e")
        self.question_meta.grid(row=0, column=1, sticky="e")
        self.stage_kicker = ctk.CTkLabel(stage_head, text="", width=1, font=(FONT, 1), text_color=MUTED)
        self.stage_kicker.grid(row=0, column=2, padx=0)

        self.stage_label = ctk.CTkLabel(self.stage_card, text="연결 대기", font=(FONT, 28, "bold"), text_color=TEXT, anchor="w")
        self.stage_label.grid(row=1, column=0, padx=22, pady=(10, 8), sticky="ew")

        flow = ctk.CTkFrame(self.stage_card, fg_color="transparent")
        flow.grid(row=2, column=0, padx=22, pady=(0, 12), sticky="ew")
        self.flow_chips: list[ctk.CTkLabel] = []
        for i, label in enumerate(("참가 모집", "문제 공개", "START", "답변 마감", "정답 공개")):
            flow.grid_columnconfigure(i, weight=1)
            chip = ctk.CTkLabel(
                flow, text=label, height=30, corner_radius=8, fg_color=PANEL_2,
                text_color=MUTED, font=(FONT, 9, "bold"),
            )
            chip.grid(row=0, column=i, padx=(0 if i == 0 else 3, 0 if i == 4 else 3), sticky="ew")
            self.flow_chips.append(chip)

        self.question_box = ctk.CTkFrame(self.stage_card, corner_radius=14, fg_color=PANEL_2)
        self.question_box.grid(row=3, column=0, padx=22, pady=(0, 12), sticky="nsew")
        self.question_box.grid_columnconfigure(0, weight=1)
        self.question_box.grid_rowconfigure(1, weight=1)
        self.question_eyebrow = ctk.CTkLabel(self.question_box, text="준비", font=(FONT, 9, "bold"), text_color=MUTED, anchor="w")
        self.question_eyebrow.grid(row=0, column=0, padx=18, pady=(15, 4), sticky="ew")
        self.question_label = ctk.CTkLabel(
            self.question_box, text="방송을 연결하거나 연습 모드를 시작하세요.",
            font=(FONT, 20, "bold"), text_color=TEXT, justify="left", anchor="nw", wraplength=720,
        )
        self.question_label.grid(row=1, column=0, padx=18, pady=(2, 16), sticky="nsew")
        self.question_box.bind("<Configure>", self._resize_question_wrap)

        self.action_hint = ctk.CTkLabel(self.stage_card, text="다음 행동  ·  방송 연결", font=(FONT, 11, "bold"), text_color=MUTED, anchor="w")
        self.action_hint.grid(row=4, column=0, padx=22, pady=(0, 6), sticky="ew")
        self.integrity_banner = ctk.CTkLabel(
            self.stage_card, text="", corner_radius=9, fg_color=("#FFF0F2", "#382027"),
            text_color=("#B93C4B", "#FF9CA8"), font=(FONT, 10, "bold"), anchor="w",
        )
        self.integrity_banner.grid(row=5, column=0, padx=22, pady=(0, 8), sticky="ew")
        self.integrity_banner.grid_remove()
        self.primary_button = ctk.CTkButton(
            self.stage_card, text="참가 모집 시작", height=64, corner_radius=13,
            font=(FONT, 17, "bold"), fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self.primary_action,
        )
        self.primary_button.grid(row=6, column=0, padx=22, pady=(0, 10), sticky="ew")

        quick = ctk.CTkFrame(self.stage_card, fg_color="transparent")
        quick.grid(row=7, column=0, padx=22, pady=(0, 18), sticky="ew")
        for i in range(4):
            quick.grid_columnconfigure(i, weight=1)
        self.force_close_btn = ctk.CTkButton(quick, text="답변 마감", height=34, corner_radius=9, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, font=(FONT, 10, "bold"), command=lambda: self.engine.close_answers())
        self.force_close_btn.grid(row=0, column=0, padx=(0, 3), sticky="ew")
        self.retry_btn = ctk.CTkButton(quick, text="문제 재진행", height=34, corner_radius=9, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, font=(FONT, 10, "bold"), command=self.retry_question)
        self.retry_btn.grid(row=0, column=1, padx=3, sticky="ew")
        ctk.CTkButton(quick, text="참가자 관리", height=34, corner_radius=9, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, font=(FONT, 10, "bold"), command=self.open_participants).grid(row=0, column=2, padx=3, sticky="ew")
        ctk.CTkButton(quick, text="운영 · 내보내기", height=34, corner_radius=9, fg_color="transparent", hover_color=PANEL_2, border_width=1, border_color=LINE, text_color=MUTED, font=(FONT, 10, "bold"), command=self.open_ops_hub).grid(row=0, column=3, padx=(3, 0), sticky="ew")

        right = ctk.CTkFrame(main, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=3)
        right.grid_rowconfigure(2, weight=2)

        stats = ctk.CTkFrame(right, fg_color="transparent")
        stats.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        for i in range(3):
            stats.grid_columnconfigure(i, weight=1)
        self.stat_part = self._stat_v8(stats, 0, "참가자")
        self.stat_ans = self._stat_v8(stats, 1, "답변")
        self.stat_correct = self._stat_v8(stats, 2, "정답")

        rank_card = ctk.CTkFrame(right, corner_radius=16, fg_color=PANEL, border_width=1, border_color=LINE)
        rank_card.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        rank_card.grid_columnconfigure(0, weight=1); rank_card.grid_rowconfigure(1, weight=1)
        rank_head = ctk.CTkFrame(rank_card, fg_color="transparent")
        rank_head.grid(row=0, column=0, padx=14, pady=(12, 4), sticky="ew"); rank_head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(rank_head, text="실시간 순위", font=(FONT, 12, "bold"), text_color=TEXT, anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(rank_head, text="TOP 10", font=(FONT, 9, "bold"), text_color=ACCENT, anchor="e").grid(row=0, column=1, sticky="e")
        self.rank_text = ctk.CTkTextbox(rank_card, corner_radius=10, fg_color=PANEL_2, border_width=0, font=(FONT, 11), activate_scrollbars=True)
        self.rank_text.grid(row=1, column=0, padx=10, pady=(4, 10), sticky="nsew"); self.rank_text.configure(state="disabled")

        answer_card = ctk.CTkFrame(right, corner_radius=16, fg_color=PANEL, border_width=1, border_color=LINE)
        answer_card.grid(row=2, column=0, sticky="nsew")
        answer_card.grid_columnconfigure(0, weight=1); answer_card.grid_rowconfigure(1, weight=1)
        answer_head = ctk.CTkFrame(answer_card, fg_color="transparent")
        answer_head.grid(row=0, column=0, padx=14, pady=(12, 4), sticky="ew"); answer_head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(answer_head, text="최근 답변", font=(FONT, 12, "bold"), text_color=TEXT, anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(answer_head, text="채팅 보기", width=74, height=26, corner_radius=8, fg_color="transparent", hover_color=PANEL_2, border_width=1, border_color=LINE, text_color=MUTED, font=(FONT, 9, "bold"), command=lambda: self.show_page("채팅")).grid(row=0, column=1, sticky="e")
        self.answer_text = ctk.CTkTextbox(answer_card, corner_radius=10, fg_color=PANEL_2, border_width=0, font=(FONT, 10), activate_scrollbars=True)
        self.answer_text.grid(row=1, column=0, padx=10, pady=(4, 10), sticky="nsew"); self.answer_text.configure(state="disabled")

        self.practice_tools = ctk.CTkFrame(right, corner_radius=12, fg_color=PANEL_2, border_width=1, border_color=LINE)
        self.practice_tools.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.practice_tools.grid_columnconfigure(0, weight=1); self.practice_tools.grid_columnconfigure(1, weight=1)
        self.practice_join_btn = ctk.CTkButton(self.practice_tools, text="테스트 참가자 +12", height=32, corner_radius=8, fg_color=PANEL_3, hover_color=LINE, text_color=TEXT, font=(FONT, 9, "bold"), command=lambda: self.engine.simulate_join(12))
        self.practice_join_btn.grid(row=0, column=0, padx=(10, 4), pady=9, sticky="ew")
        self.practice_answer_btn = ctk.CTkButton(self.practice_tools, text="테스트 답변 생성", height=32, corner_radius=8, fg_color=PANEL_3, hover_color=LINE, text_color=TEXT, font=(FONT, 9, "bold"), command=self.engine.simulate_answers)
        self.practice_answer_btn.grid(row=0, column=1, padx=(4, 10), pady=9, sticky="ew")
        self.practice_tools.grid_remove()

        self.health_bar = ctk.CTkFrame(body, height=40, corner_radius=12, fg_color=PANEL, border_width=1, border_color=LINE)
        self.health_bar.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.health_bar.grid_columnconfigure(2, weight=1)
        self.run_ws_status = ctk.CTkLabel(self.health_bar, text="● WebSocket 확인 중", font=(FONT, 9, "bold"), text_color=MUTED)
        self.run_ws_status.grid(row=0, column=0, padx=(12, 8), pady=8, sticky="w")
        self.pipeline_label = ctk.CTkLabel(self.health_bar, text="수집 파이프라인 확인 중", font=(FONT, 9), text_color=MUTED)
        self.pipeline_label.grid(row=0, column=1, padx=8, pady=8, sticky="w")
        self.run_last_chat = ctk.CTkLabel(self.health_bar, text="참가자 채팅: 아직 없음", font=(FONT, 9), text_color=MUTED, anchor="e")
        self.run_last_chat.grid(row=0, column=2, padx=(8, 12), pady=8, sticky="ew")

        self.recovery_button = ctk.CTkButton(body, text="이전 세션 복구", height=32, corner_radius=9, fg_color=PURPLE, hover_color="#6652C4", font=(FONT, 10, "bold"), command=self.restore_recovery)
        if isinstance(self._pending_recovery, dict) and self._pending_recovery.get("hadSession"):
            self.recovery_button.grid(row=3, column=0, sticky="ew", pady=(8, 0))

        self._apply_live_mode_ui()
        return page

    def _stat_v8(self, parent: ctk.CTkFrame, col: int, label: str) -> ctk.CTkLabel:
        card = ctk.CTkFrame(parent, corner_radius=13, fg_color=PANEL, border_width=1, border_color=LINE)
        card.grid(row=0, column=col, padx=(0 if col == 0 else 3, 0 if col == 2 else 3), sticky="ew")
        ctk.CTkLabel(card, text=label, font=(FONT, 9, "bold"), text_color=MUTED).pack(anchor="w", padx=11, pady=(9, 0))
        value = ctk.CTkLabel(card, text="0", font=(FONT, 24, "bold"), text_color=TEXT)
        value.pack(anchor="w", padx=11, pady=(0, 8))
        return value

    def _resize_question_wrap(self, event) -> None:
        try:
            self.question_label.configure(wraplength=max(360, int(event.width) - 44))
        except Exception:
            pass

    # ---------- safer broadcast lock ----------
    def _toggle_live_lock(self) -> None:
        desired = not bool(self.live_mode_var.get())
        active = self.engine.state not in {"DISCONNECTED", "READY", "FINISHED"}
        if not desired and active:
            if not messagebox.askyesno("방송 잠금 해제", "퀴즈가 진행 중입니다. 편집과 설정 잠금을 해제할까요?"):
                return
        self._set_live_mode(desired)

    def _toggle_live_mode_hotkey(self) -> None:
        self._toggle_live_lock()

    def _apply_live_mode_ui(self) -> None:
        enabled = bool(self.live_mode_var.get())
        active = self.engine.state not in {"DISCONNECTED", "READY", "FINISHED"}
        if hasattr(self, "live_lock_button"):
            self.live_lock_button.configure(
                text="LIVE 잠금 ON" if enabled else "방송 잠금",
                fg_color=LIVE_RED if enabled else PANEL_2,
                hover_color="#D84452" if enabled else PANEL_3,
                text_color="#FFFFFF" if enabled else TEXT,
                border_width=0 if enabled else 1,
            )
        for key in ("문제", "설정"):
            if hasattr(self, "nav_buttons") and key in self.nav_buttons:
                self.nav_buttons[key].configure(state="disabled" if enabled else "normal")
        if hasattr(self, "theme_button"):
            self.theme_button.configure(state="disabled" if enabled else "normal")
        if hasattr(self, "run_set_menu"):
            self.run_set_menu.configure(state="disabled" if (enabled or active) else "normal")
        if hasattr(self, "edit_quiz_button"):
            self.edit_quiz_button.configure(state="disabled" if (enabled or active) else "normal")
        if hasattr(self, "practice_button"):
            self.practice_button.configure(state="disabled" if enabled else "normal")
        if hasattr(self, "streamer_entry"):
            lock_entry = enabled or self.engine.connected or self.engine.practice_mode
            self.streamer_entry.configure(state="disabled" if lock_entry else "normal")
        if hasattr(self, "connect_button") and enabled:
            self.connect_button.configure(state="disabled")
        if hasattr(self, "side_mode"):
            if enabled:
                self.side_mode.configure(text="LIVE 잠금", text_color=LIVE_RED)

    def _render_run_state(self) -> None:
        # Use the stable v0.6 render chain, then apply the new v0.8 layout rules.
        QuizAppV6._render_run_state(self)
        if not hasattr(self, "stage_state_chip"):
            return

        state = self.engine.state
        meta = {
            "DISCONNECTED": ("OFFLINE", MUTED),
            "READY": ("READY", GOOD),
            "RECRUITING": ("모집 중", ACCENT),
            "LOCKED": ("문제 준비", ACCENT),
            "QUESTION_SHOWN": ("문제 공개", WARNING),
            "ANSWERING": ("답변 접수", GOOD),
            "QUESTION_CLOSED": ("마감", WARNING),
            "ANSWER_REVEALED": ("정답 공개", PURPLE),
            "QUESTION_VOID": ("문제 무효", DANGER),
            "FINISHED": ("종료", PURPLE),
        }.get(state, (state, MUTED))
        self.stage_state_chip.configure(text=meta[0], text_color=meta[1], fg_color=PANEL_2)
        self.stage_card.configure(border_color=LINE, border_width=1)

        active_step = {
            "RECRUITING": 0,
            "LOCKED": 1,
            "QUESTION_SHOWN": 1,
            "ANSWERING": 2,
            "QUESTION_CLOSED": 3,
            "ANSWER_REVEALED": 4,
            "QUESTION_VOID": 4,
            "FINISHED": 4,
        }.get(state, -1)
        for idx, chip in enumerate(self.flow_chips):
            if idx == active_step:
                chip.configure(fg_color=ACCENT, text_color="#FFFFFF")
            elif idx < active_step:
                chip.configure(fg_color=PANEL_3, text_color=GOOD)
            else:
                chip.configure(fg_color=PANEL_2, text_color=MUTED)

        q = self.engine.current_question
        count = len(self.engine.questions)
        if state == "DISCONNECTED":
            self.question_meta.configure(text=self.active_set_name)
            self.question_eyebrow.configure(text="준비")
            self.question_label.configure(text="방송을 연결하거나 연습 모드를 시작하세요.", text_color=MUTED)
        elif state == "READY":
            self.question_meta.configure(text=self.active_set_name)
            self.question_eyebrow.configure(text="퀴즈 준비 완료")
            self.question_label.configure(text=f"{count}개 문제가 준비되어 있습니다. 참가 모집을 시작하세요.", text_color=TEXT)
        elif state == "RECRUITING":
            self.question_meta.configure(text=f"참가자 {len(self.engine.participants):,}명")
            self.question_eyebrow.configure(text="참가 모집")
            self.question_label.configure(text="시청자가 채팅에 !참여 를 입력하면 참가자로 등록됩니다.", text_color=TEXT)
        elif q:
            self.question_meta.configure(text=f"Q{self.engine.current_index + 1} / {count}")
            self.question_eyebrow.configure(text="현재 문제")
            self.question_label.configure(text=q.prompt, text_color=TEXT)
        else:
            self.question_meta.configure(text="문제 없음")
            self.question_eyebrow.configure(text="확인 필요")
            self.question_label.configure(text="문제가 없습니다. 문제 편집에서 문제를 추가하세요.", text_color=MUTED)

        _k, _stage, action = self._stage_info(state)
        self.action_hint.configure(text=f"다음 행동  ·  {action}")
        self.primary_button.configure(height=64, font=(FONT, 17, "bold"))
        if state == "ANSWERING":
            self.primary_button.configure(fg_color=GOOD, hover_color="#289A68")
        elif state == "QUESTION_CLOSED":
            self.primary_button.configure(fg_color=PURPLE, hover_color="#6652C4")
        elif state == "QUESTION_VOID":
            self.primary_button.configure(fg_color=DANGER, hover_color="#C94755")
        else:
            self.primary_button.configure(fg_color=ACCENT, hover_color=ACCENT_HOVER)

        if self.engine.practice_mode:
            self.practice_tools.grid()
            self.practice_button.configure(text="연습 종료")
        else:
            self.practice_tools.grid_remove()
            self.practice_button.configure(text="연습")

        self._apply_live_mode_ui()

    # ---------- advanced operations are one level deeper ----------
    def open_ops_hub(self) -> None:
        win = ctk.CTkToplevel(self)
        win.title("운영 · 내보내기")
        win.geometry("520x330")
        win.configure(fg_color=BG)
        win.transient(self); win.grab_set(); win.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(win, text="운영 · 내보내기", font=(FONT, 20, "bold"), text_color=TEXT, anchor="w").grid(row=0, column=0, padx=22, pady=(20, 4), sticky="ew")
        ctk.CTkLabel(win, text="방송 중 자주 쓰지 않는 기능은 여기로 모았습니다.", font=(FONT, 10), text_color=MUTED, anchor="w").grid(row=1, column=0, padx=22, pady=(0, 14), sticky="ew")
        grid = ctk.CTkFrame(win, fg_color="transparent")
        grid.grid(row=2, column=0, padx=22, pady=0, sticky="nsew")
        grid.grid_columnconfigure(0, weight=1); grid.grid_columnconfigure(1, weight=1)
        actions = [
            ("문제 무효", "현재 문제 점수 롤백", self.void_question, DANGER),
            ("수동 판정", "예외 답변 정답/오답 처리", self.open_adjudication, PANEL_2),
            ("점수 · 탈락", "운영 보정 및 참가 상태 변경", self.open_participant_ops, PANEL_2),
            ("결과 CSV", "현재 결과 파일로 저장", self.export_results_csv, PANEL_2),
        ]
        for i, (title, desc, command, color) in enumerate(actions):
            card = ctk.CTkButton(
                grid, text=f"{title}\n{desc}", height=74, corner_radius=12,
                fg_color=color, hover_color=PANEL_3 if color == PANEL_2 else "#C94755",
                text_color="#FFFFFF" if color == DANGER else TEXT,
                font=(FONT, 11, "bold"), anchor="w",
                command=lambda c=command: self._launch_ops(win, c),
            )
            card.grid(row=i // 2, column=i % 2, padx=(0 if i % 2 == 0 else 5, 5 if i % 2 == 0 else 0), pady=5, sticky="ew")

    @staticmethod
    def _launch_ops(win, command) -> None:
        win.destroy()
        command()

    # ---------- onboarding ----------
    def show_onboarding(self) -> None:
        win = ctk.CTkToplevel(self)
        win.title("SOOP Quiz Studio 시작하기")
        win.geometry("700x430")
        win.configure(fg_color=BG)
        win.transient(self); win.grab_set(); win.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(win, text="방송 준비는 세 단계면 됩니다", font=(FONT, 24, "bold"), text_color=TEXT, anchor="w").grid(row=0, column=0, padx=28, pady=(26, 4), sticky="ew")
        ctk.CTkLabel(win, text="방송 중에는 ‘방송 진행’ 화면의 큰 버튼만 따라가면 됩니다.", font=(FONT, 11), text_color=MUTED, anchor="w").grid(row=1, column=0, padx=28, pady=(0, 14), sticky="ew")
        steps = [
            ("1", "방송 연결", "SOOP 방송국 ID를 입력하고 연결합니다."),
            ("2", "문제와 레이어 준비", "문제를 확인하고 퀴즈/TOP10 브라우저 레이어를 등록합니다."),
            ("3", "참가 모집 시작", "모집 시작과 동시에 방송 잠금이 켜져 편집 실수를 막습니다."),
        ]
        for row, (no, title, desc) in enumerate(steps, start=2):
            card = ctk.CTkFrame(win, corner_radius=12, fg_color=PANEL, border_width=1, border_color=LINE)
            card.grid(row=row, column=0, padx=28, pady=5, sticky="ew"); card.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(card, text=no, width=34, height=34, corner_radius=9, fg_color=ACCENT, text_color="#FFFFFF", font=(FONT, 13, "bold")).grid(row=0, column=0, padx=12, pady=10)
            wrap = ctk.CTkFrame(card, fg_color="transparent"); wrap.grid(row=0, column=1, padx=(0, 12), pady=8, sticky="ew")
            ctk.CTkLabel(wrap, text=title, font=(FONT, 12, "bold"), text_color=TEXT, anchor="w").pack(fill="x")
            ctk.CTkLabel(wrap, text=desc, font=(FONT, 9), text_color=MUTED, anchor="w").pack(fill="x", pady=(2, 0))

        def done() -> None:
            self.settings["onboarding_done_v8"] = True
            self._save_settings()
            win.destroy()

        ctk.CTkButton(win, text="시작", height=42, corner_radius=10, fg_color=ACCENT, hover_color=ACCENT_HOVER, font=(FONT, 11, "bold"), command=done).grid(row=5, column=0, padx=28, pady=(14, 24), sticky="ew")


def _single_instance() -> bool:
    if sys.platform != "win32":
        return True
    try:
        kernel = ctypes.windll.kernel32
        handle = kernel.CreateMutexW(None, False, "SOOPQuizStudio-v0.8-single-instance")
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
    QuizAppV8().mainloop()


if __name__ == "__main__":
    main()
