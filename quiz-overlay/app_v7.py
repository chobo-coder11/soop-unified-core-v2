from __future__ import annotations

import ctypes
import sys

import customtkinter as ctk
from tkinter import messagebox

from app_v6 import QuizAppV6
from common import APP_NAME, SESSION_FILE, SETTINGS_FILE
from core_runtime import BundledCoreRuntime
from overlay_server_v7 import OverlayServerV7
from quiz_engine_v7 import QuizEngineV7, UI_VERSION
from soop_client_v5 import SoopChatClientV5


FONT = "Malgun Gothic"
BG = ("#F5F7FA", "#080B10")
PANEL = ("#FFFFFF", "#10151D")
PANEL_2 = ("#F0F3F7", "#171D26")
PANEL_3 = ("#E7ECF3", "#202835")
LINE = ("#D9E0E9", "#283342")
TEXT = ("#141922", "#F7F9FC")
MUTED = ("#667385", "#9BA8BA")
ACCENT = "#4B72FF"
ACCENT_HOVER = "#3E61DF"
GOOD = "#2CAE78"
DANGER = "#E24F61"
WARNING = "#D79225"
PURPLE = "#7A63E5"
LIVE_RED = "#F04455"


class QuizAppV7(QuizAppV6):
    """Broadcast-first v0.7 controller.

    The hardened quiz engine and socket pipeline are kept intact. This layer is
    intentionally focused on readability, operator safety and one-glance live
    control for streamers who may be watching the app from a second monitor.
    """

    def __init__(self) -> None:
        # Enlarge inherited editor/chat/settings controls too, not only the run page.
        ctk.set_widget_scaling(1.08)
        self._recovery_last_write = 0.0
        self._recovery_signature = None
        self.settings = self._load_json(SETTINGS_FILE, {})
        appearance = str(self.settings.get("appearance", "dark")).lower()
        ctk.set_appearance_mode({"light": "Light", "system": "System"}.get(appearance, "Dark"))
        ctk.set_default_color_theme("blue")
        ctk.CTk.__init__(self)
        self.title(f"{APP_NAME} · {UI_VERSION}")
        self.geometry("1560x960")
        self.minsize(1180, 700)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.engine = QuizEngineV7()
        self.runtime = BundledCoreRuntime()
        self.client = SoopChatClientV5(self.engine, self._socket_status)
        self.overlay = OverlayServerV7(self.engine)
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
        if not self.settings.get("onboarding_done_v7"):
            self.after(500, self.show_onboarding)

    # ---------- shell / navigation ----------
    def _build_shell(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.topbar = ctk.CTkFrame(self, height=82, corner_radius=0, fg_color=PANEL)
        self.topbar.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self.topbar.grid_columnconfigure(1, weight=1)

        brand = ctk.CTkFrame(self.topbar, fg_color="transparent")
        brand.grid(row=0, column=0, padx=(24, 12), pady=12, sticky="w")
        mark = ctk.CTkFrame(brand, width=42, height=42, corner_radius=12, fg_color=ACCENT)
        mark.pack(side="left", padx=(0, 12)); mark.pack_propagate(False)
        ctk.CTkLabel(mark, text="Q", font=(FONT, 20, "bold"), text_color="#FFFFFF").place(relx=.5, rely=.5, anchor="center")
        text = ctk.CTkFrame(brand, fg_color="transparent"); text.pack(side="left")
        ctk.CTkLabel(text, text="SOOP QUIZ STUDIO", font=(FONT, 19, "bold"), text_color=TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(text, text=f"방송 진행 콘솔  ·  v{UI_VERSION}", font=(FONT, 11), text_color=MUTED, anchor="w").pack(anchor="w", pady=(1, 0))

        self.top_status = ctk.CTkLabel(self.topbar, text="●  방송 엔진 준비 중", font=(FONT, 13, "bold"), text_color=MUTED)
        self.top_status.grid(row=0, column=1, padx=12, sticky="e")

        self.live_badge = ctk.CTkLabel(self.topbar, text="SAFE", width=64, height=34, corner_radius=10, fg_color=PANEL_2, text_color=MUTED, font=(FONT, 11, "bold"))
        self.live_badge.grid(row=0, column=2, padx=(4, 5), pady=16)
        self.live_switch = ctk.CTkSwitch(self.topbar, text="LIVE MODE", variable=self.live_mode_var, font=(FONT, 12, "bold"), command=self._live_switch_changed, progress_color=LIVE_RED, button_color="#FFFFFF", button_hover_color="#F1F3F6")
        self.live_switch.grid(row=0, column=3, padx=(4, 12), pady=16)
        self.theme_button = ctk.CTkButton(self.topbar, text=self._theme_button_text(), width=90, height=38, corner_radius=11, fg_color=PANEL_2, hover_color=PANEL_3, border_width=1, border_color=LINE, text_color=TEXT, font=(FONT, 11, "bold"), command=self.toggle_appearance)
        self.theme_button.grid(row=0, column=4, padx=(0, 22), pady=16)

        self.sidebar = ctk.CTkFrame(self, width=238, corner_radius=0, fg_color=("#EDF1F6", "#0D1218"))
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(8, weight=1)
        ctk.CTkLabel(self.sidebar, text="방송 도구", font=(FONT, 12, "bold"), text_color=MUTED, anchor="w").grid(row=0, column=0, padx=18, pady=(22, 9), sticky="ew")

        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        nav = [("진행", "방송 진행"), ("문제", "문제 편집"), ("채팅", "참가자 채팅"), ("레이어", "방송 레이어"), ("설정", "설정 · 진단")]
        for idx, (key, label) in enumerate(nav, start=1):
            btn = ctk.CTkButton(self.sidebar, text=label, height=52, anchor="w", corner_radius=12, fg_color="transparent", hover_color=("#E0E6EF", "#19212C"), text_color=TEXT, font=(FONT, 14, "bold"), command=lambda k=key: self.show_page(k))
            btn.grid(row=idx, column=0, padx=12, pady=4, sticky="ew")
            self.nav_buttons[key] = btn

        self.side_status = ctk.CTkFrame(self.sidebar, corner_radius=16, fg_color=PANEL, border_width=1, border_color=LINE)
        self.side_status.grid(row=9, column=0, padx=12, pady=14, sticky="ew")
        ctk.CTkLabel(self.side_status, text="현재 세션", font=(FONT, 10, "bold"), text_color=MUTED, anchor="w").pack(fill="x", padx=14, pady=(12, 2))
        self.side_mode = ctk.CTkLabel(self.side_status, text="대기 중", font=(FONT, 14, "bold"), text_color=MUTED, anchor="w")
        self.side_mode.pack(fill="x", padx=14)
        self.side_help = ctk.CTkLabel(self.side_status, text="Space = 다음 단계\nF9 = LIVE MODE", font=(FONT, 10), text_color=MUTED, justify="left", anchor="w")
        self.side_help.pack(fill="x", padx=14, pady=(4, 12))

        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color=BG)
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

    def show_page(self, name: str) -> None:
        if bool(self.live_mode_var.get()) and name in {"문제", "설정"}:
            self._flash_top("LIVE MODE에서는 문제 편집과 설정을 잠급니다.", WARNING)
            return
        self._active_page = name
        for key, button in self.nav_buttons.items():
            selected = key == name
            button.configure(
                fg_color=("#DBE5FF", "#182541") if selected else "transparent",
                text_color=("#2E58C8", "#E8EEFF") if selected else TEXT,
                border_width=1 if selected else 0,
                border_color=("#C6D5FF", "#2B4274") if selected else LINE,
            )
        for page in self._pages.values(): page.grid_remove()
        if name not in self._pages:
            builders = {"진행": self._build_run_page, "문제": self._build_editor_page, "채팅": self._build_chat_page, "레이어": self._build_overlay_page, "설정": self._build_settings_page}
            self._pages[name] = builders[name]()
        self._pages[name].grid(row=0, column=0, sticky="nsew")
        self._last_ui_version = -1
        if name == "채팅": self._render_chat_page(force=True)
        else: self._refresh_active_page(force=True)

    def _page(self, title: str, subtitle: str) -> tuple[ctk.CTkFrame, ctk.CTkFrame]:
        page = ctk.CTkFrame(self.content, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1); page.grid_rowconfigure(1, weight=1)
        head = ctk.CTkFrame(page, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=30, pady=(20, 12))
        ctk.CTkLabel(head, text=title, font=(FONT, 30, "bold"), text_color=TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(head, text=subtitle, font=(FONT, 13), text_color=MUTED, anchor="w").pack(anchor="w", pady=(3, 0))
        body = ctk.CTkFrame(page, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=30, pady=(0, 22))
        return page, body

    # ---------- broadcast console ----------
    def _build_run_page(self) -> ctk.CTkFrame:
        page, body = self._page("방송 진행", "현재 상태 → 지금 할 일 → 참가/답변 현황 순서만 보면 됩니다. 단계는 자동으로 넘어가지 않습니다.")
        body.grid_columnconfigure(0, weight=1); body.grid_rowconfigure(1, weight=1)

        self.command_bar = ctk.CTkFrame(body, corner_radius=16, fg_color=PANEL, border_width=1, border_color=LINE)
        self.command_bar.grid(row=0, column=0, sticky="ew", pady=(0, 11))
        self.command_bar.grid_columnconfigure(1, weight=1); self.command_bar.grid_columnconfigure(5, weight=1)
        ctk.CTkLabel(self.command_bar, text="방송국", font=(FONT, 12, "bold"), text_color=MUTED).grid(row=0, column=0, padx=(16, 8), pady=12)
        self.streamer_var = ctk.StringVar(value=str(self.settings.get("streamer", "")))
        self.streamer_entry = ctk.CTkEntry(self.command_bar, textvariable=self.streamer_var, height=42, corner_radius=10, placeholder_text="SOOP 방송국 ID", border_color=LINE, fg_color=PANEL_2, font=(FONT, 13))
        self.streamer_entry.grid(row=0, column=1, padx=5, pady=9, sticky="ew")
        self.connect_button = ctk.CTkButton(self.command_bar, text="방송 연결", width=104, height=42, corner_radius=10, fg_color=ACCENT, hover_color=ACCENT_HOVER, font=(FONT, 13, "bold"), command=self.connect_broadcast)
        self.connect_button.grid(row=0, column=2, padx=5, pady=9)
        self.practice_button = ctk.CTkButton(self.command_bar, text="연습", width=78, height=42, corner_radius=10, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, font=(FONT, 12, "bold"), command=self.toggle_practice)
        self.practice_button.grid(row=0, column=3, padx=(5, 14), pady=9)
        ctk.CTkFrame(self.command_bar, width=1, height=30, fg_color=LINE).grid(row=0, column=4, padx=(2, 14))
        ctk.CTkLabel(self.command_bar, text="퀴즈", font=(FONT, 12, "bold"), text_color=MUTED).grid(row=0, column=5, padx=(0, 7), pady=12, sticky="e")
        self.run_set_var = ctk.StringVar(value=self.active_set_name)
        self.run_set_menu = ctk.CTkOptionMenu(self.command_bar, variable=self.run_set_var, values=list(self.quiz_sets), height=42, corner_radius=10, font=(FONT, 12, "bold"), command=self._change_active_set)
        self.run_set_menu.grid(row=0, column=6, padx=5, pady=9, sticky="ew")
        ctk.CTkButton(self.command_bar, text="편집", width=70, height=42, corner_radius=10, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, font=(FONT, 12, "bold"), command=lambda: self.show_page("문제")).grid(row=0, column=7, padx=(5, 16), pady=9)

        main = ctk.CTkFrame(body, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew")
        main.grid_columnconfigure(0, weight=8); main.grid_columnconfigure(1, weight=4); main.grid_rowconfigure(0, weight=1)

        self.stage_card = ctk.CTkFrame(main, corner_radius=24, fg_color=PANEL, border_width=1, border_color=LINE)
        self.stage_card.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self.stage_card.grid_columnconfigure(0, weight=1); self.stage_card.grid_rowconfigure(4, weight=1)
        top = ctk.CTkFrame(self.stage_card, fg_color="transparent")
        top.grid(row=0, column=0, padx=28, pady=(24, 0), sticky="ew"); top.grid_columnconfigure(1, weight=1)
        self.stage_state_chip = ctk.CTkLabel(top, text="OFFLINE", corner_radius=999, fg_color=PANEL_2, text_color=MUTED, font=(FONT, 11, "bold"), padx=12, pady=7)
        self.stage_state_chip.grid(row=0, column=0, sticky="w")
        self.stage_kicker = ctk.CTkLabel(top, text="READY", font=(FONT, 12, "bold"), text_color=ACCENT, anchor="e")
        self.stage_kicker.grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(self.stage_card, text="현재 상태", font=(FONT, 12, "bold"), text_color=MUTED, anchor="w").grid(row=1, column=0, padx=28, pady=(18, 0), sticky="ew")
        self.stage_label = ctk.CTkLabel(self.stage_card, text="연결 대기", font=(FONT, 36, "bold"), text_color=TEXT, anchor="w")
        self.stage_label.grid(row=2, column=0, padx=28, pady=(2, 0), sticky="ew")
        self.action_hint = ctk.CTkLabel(self.stage_card, text="지금 할 일  →  방송 연결", font=(FONT, 16, "bold"), text_color=ACCENT, anchor="w")
        self.action_hint.grid(row=3, column=0, padx=28, pady=(8, 0), sticky="ew")
        self.question_label = ctk.CTkLabel(self.stage_card, text="SOOP 방송을 연결하거나 연습 모드를 켜주세요.", font=(FONT, 24, "bold"), text_color=MUTED, justify="left", anchor="nw", wraplength=780)
        self.question_label.grid(row=4, column=0, padx=28, pady=(20, 16), sticky="nsew")
        self.integrity_banner = ctk.CTkLabel(self.stage_card, text="", corner_radius=11, fg_color=("#FFF0F2", "#3A1F26"), text_color=("#B73748", "#FF9EAA"), font=(FONT, 13, "bold"), anchor="w")
        self.integrity_banner.grid(row=5, column=0, padx=28, pady=(0, 10), sticky="ew"); self.integrity_banner.grid_remove()
        ctk.CTkLabel(self.stage_card, text="다음 단계", font=(FONT, 12, "bold"), text_color=MUTED, anchor="w").grid(row=6, column=0, padx=28, pady=(4, 6), sticky="ew")
        self.primary_button = ctk.CTkButton(self.stage_card, text="참가 모집 시작", height=88, corner_radius=18, font=(FONT, 22, "bold"), fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self.primary_action)
        self.primary_button.grid(row=7, column=0, padx=28, pady=(0, 14), sticky="ew")
        self.quick_tools = ctk.CTkFrame(self.stage_card, fg_color="transparent")
        self.quick_tools.grid(row=8, column=0, padx=28, pady=(0, 24), sticky="ew")
        for i in range(4): self.quick_tools.grid_columnconfigure(i, weight=1)
        self.force_close_btn = ctk.CTkButton(self.quick_tools, text="답변 마감", height=40, corner_radius=10, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, font=(FONT, 12, "bold"), command=lambda: self.engine.close_answers())
        self.force_close_btn.grid(row=0, column=0, padx=(0, 4), sticky="ew")
        self.retry_btn = ctk.CTkButton(self.quick_tools, text="문제 재진행", height=40, corner_radius=10, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, font=(FONT, 12, "bold"), command=self.retry_question)
        self.retry_btn.grid(row=0, column=1, padx=4, sticky="ew")
        ctk.CTkButton(self.quick_tools, text="참가자 관리", height=40, corner_radius=10, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, font=(FONT, 12, "bold"), command=self.open_participants).grid(row=0, column=2, padx=4, sticky="ew")
        ctk.CTkButton(self.quick_tools, text="결과 CSV", height=40, corner_radius=10, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, font=(FONT, 12, "bold"), command=self.export_results_csv).grid(row=0, column=3, padx=(4, 0), sticky="ew")

        right = ctk.CTkFrame(main, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(7, 0)); right.grid_columnconfigure(0, weight=1); right.grid_rowconfigure(2, weight=1)
        stats = ctk.CTkFrame(right, fg_color="transparent"); stats.grid(row=0, column=0, sticky="ew")
        for i in range(3): stats.grid_columnconfigure(i, weight=1)
        self.stat_part = self._stat_v7(stats, 0, "참가")
        self.stat_ans = self._stat_v7(stats, 1, "답변")
        self.stat_correct = self._stat_v7(stats, 2, "정답")

        self.practice_tools = ctk.CTkFrame(right, corner_radius=16, fg_color=PANEL, border_width=1, border_color=LINE)
        self.practice_tools.grid(row=1, column=0, sticky="ew", pady=(10, 10)); self.practice_tools.grid_columnconfigure(0, weight=1); self.practice_tools.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.practice_tools, text="연습 도구", font=(FONT, 12, "bold"), text_color=MUTED, anchor="w").grid(row=0, column=0, columnspan=2, padx=14, pady=(11, 6), sticky="ew")
        self.practice_join_btn = ctk.CTkButton(self.practice_tools, text="참가자 +12", height=36, corner_radius=9, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, font=(FONT, 11, "bold"), command=lambda: self.engine.simulate_join(12))
        self.practice_join_btn.grid(row=1, column=0, padx=(14, 4), pady=(0, 12), sticky="ew")
        self.practice_answer_btn = ctk.CTkButton(self.practice_tools, text="테스트 답변", height=36, corner_radius=9, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, font=(FONT, 11, "bold"), command=self.engine.simulate_answers)
        self.practice_answer_btn.grid(row=1, column=1, padx=(4, 14), pady=(0, 12), sticky="ew")

        tabs = ctk.CTkTabview(right, corner_radius=18, fg_color=PANEL, segmented_button_fg_color=PANEL_2, segmented_button_selected_color=ACCENT, segmented_button_selected_hover_color=ACCENT_HOVER)
        tabs.grid(row=2, column=0, sticky="nsew"); tabs.add("TOP 10"); tabs.add("답변 현황")
        self.rank_text = ctk.CTkTextbox(tabs.tab("TOP 10"), corner_radius=11, fg_color=PANEL_2, border_width=0, font=(FONT, 14), activate_scrollbars=True)
        self.rank_text.pack(fill="both", expand=True, padx=9, pady=9); self.rank_text.configure(state="disabled")
        self.answer_text = ctk.CTkTextbox(tabs.tab("답변 현황"), corner_radius=11, fg_color=PANEL_2, border_width=0, font=(FONT, 13), activate_scrollbars=True)
        self.answer_text.pack(fill="both", expand=True, padx=9, pady=9); self.answer_text.configure(state="disabled")

        self.health_bar = ctk.CTkFrame(body, corner_radius=14, fg_color=PANEL, border_width=1, border_color=LINE)
        self.health_bar.grid(row=2, column=0, sticky="ew", pady=(11, 0)); self.health_bar.grid_columnconfigure(2, weight=1)
        self.run_ws_status = ctk.CTkLabel(self.health_bar, text="● WebSocket 확인 중", font=(FONT, 11, "bold"), text_color=MUTED)
        self.run_ws_status.grid(row=0, column=0, padx=(14, 8), pady=10, sticky="w")
        self.pipeline_label = ctk.CTkLabel(self.health_bar, text="수집 파이프라인 확인 중", font=(FONT, 11), text_color=MUTED)
        self.pipeline_label.grid(row=0, column=1, padx=8, pady=10, sticky="w")
        self.run_last_chat = ctk.CTkLabel(self.health_bar, text="참가자 채팅: 아직 없음", font=(FONT, 11), text_color=MUTED, anchor="e")
        self.run_last_chat.grid(row=0, column=2, padx=(8, 14), pady=10, sticky="ew")

        self.ops_bar = ctk.CTkFrame(body, fg_color="transparent")
        self.ops_bar.grid(row=3, column=0, sticky="ew", pady=(8, 0)); self.ops_bar.grid_columnconfigure(4, weight=1)
        ctk.CTkLabel(self.ops_bar, text="비상 운영", font=(FONT, 10, "bold"), text_color=MUTED).grid(row=0, column=0, padx=(2, 8), pady=7)
        ctk.CTkButton(self.ops_bar, text="문제 무효", width=90, height=34, corner_radius=9, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, command=self.void_question).grid(row=0, column=1, padx=4)
        ctk.CTkButton(self.ops_bar, text="수동 판정", width=90, height=34, corner_radius=9, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, command=self.open_adjudication).grid(row=0, column=2, padx=4)
        ctk.CTkButton(self.ops_bar, text="점수 · 탈락", width=106, height=34, corner_radius=9, fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT, command=self.open_participant_ops).grid(row=0, column=3, padx=4)
        ctk.CTkButton(self.ops_bar, text="참가자 채팅", width=110, height=34, corner_radius=9, fg_color="transparent", border_width=1, border_color=LINE, hover_color=PANEL_2, text_color=MUTED, command=lambda: self.show_page("채팅")).grid(row=0, column=5, padx=(8, 0), sticky="e")

        self.recovery_button = ctk.CTkButton(body, text="이전 세션 복구", height=36, corner_radius=10, fg_color=PURPLE, hover_color="#6B54D0", font=(FONT, 12, "bold"), command=self.restore_recovery)
        if isinstance(self._pending_recovery, dict) and self._pending_recovery.get("hadSession"):
            self.recovery_button.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        self._apply_live_mode_ui()
        return page

    def _stat_v7(self, parent: ctk.CTkFrame, col: int, label: str) -> ctk.CTkLabel:
        box = ctk.CTkFrame(parent, corner_radius=16, fg_color=PANEL, border_width=1, border_color=LINE)
        box.grid(row=0, column=col, padx=(0 if col == 0 else 4, 0 if col == 2 else 4), sticky="ew")
        ctk.CTkLabel(box, text=label, font=(FONT, 10, "bold"), text_color=MUTED).pack(anchor="w", padx=13, pady=(11, 0))
        value = ctk.CTkLabel(box, text="0", font=(FONT, 32, "bold"), text_color=TEXT)
        value.pack(anchor="w", padx=13, pady=(0, 10))
        return value

    # ---------- LIVE MODE ----------
    def primary_action(self) -> None:
        before = self.engine.state
        super().primary_action()
        if before == "READY" and self.engine.state == "RECRUITING" and not self.engine.practice_mode:
            self._set_live_mode(True)

    def _live_switch_changed(self) -> None:
        desired = bool(self.live_mode_var.get())
        active = self.engine.state not in {"DISCONNECTED", "READY", "FINISHED"}
        if not desired and active:
            if not messagebox.askyesno("LIVE MODE 해제", "퀴즈가 진행 중입니다. LIVE MODE를 해제하면 편집/설정 메뉴가 다시 활성화됩니다.\n\n해제할까요?"):
                self.live_mode_var.set(True)
                return
        self._set_live_mode(desired)

    def _toggle_live_mode_hotkey(self) -> None:
        self.live_mode_var.set(not bool(self.live_mode_var.get()))
        self._live_switch_changed()

    def _set_live_mode(self, enabled: bool) -> None:
        self.live_mode_var.set(bool(enabled))
        if enabled and self._active_page in {"문제", "설정"}:
            self.show_page("진행")
        self._apply_live_mode_ui()

    def _apply_live_mode_ui(self) -> None:
        enabled = bool(self.live_mode_var.get())
        if hasattr(self, "live_badge"):
            self.live_badge.configure(text="● LIVE" if enabled else "SAFE", fg_color=LIVE_RED if enabled else PANEL_2, text_color="#FFFFFF" if enabled else MUTED)
        for key in ("문제", "설정"):
            if hasattr(self, "nav_buttons") and key in self.nav_buttons:
                self.nav_buttons[key].configure(state="disabled" if enabled else "normal")
        if hasattr(self, "theme_button"):
            self.theme_button.configure(state="disabled" if enabled else "normal")
        if hasattr(self, "command_bar"):
            if enabled: self.command_bar.grid_remove()
            else: self.command_bar.grid()
        if hasattr(self, "ops_bar"):
            if enabled: self.ops_bar.grid_remove()
            else: self.ops_bar.grid()
        if hasattr(self, "recovery_button") and enabled:
            self.recovery_button.grid_remove()
        if hasattr(self, "stage_card"):
            self.primary_button.configure(height=98 if enabled else 88, font=(FONT, 24 if enabled else 22, "bold"))
        if hasattr(self, "side_mode"):
            self.side_mode.configure(text="LIVE MODE" if enabled else ("연습 모드" if self.engine.practice_mode else "대기/진행"), text_color=LIVE_RED if enabled else MUTED)

    def _render_run_state(self) -> None:
        super()._render_run_state()
        if not hasattr(self, "stage_state_chip"):
            return
        _k, _s, action = self._stage_info(self.engine.state)
        self.action_hint.configure(text=f"지금 할 일  →  {action}")
        if bool(self.live_mode_var.get()):
            self.stage_card.configure(border_width=2)
        self._apply_live_mode_ui()

    def void_question(self) -> None:
        if bool(self.live_mode_var.get()):
            if not messagebox.askyesno("문제 무효 확인", "현재 문제를 무효 처리하면 이 문제의 점수가 롤백됩니다.\n\n정말 문제를 무효 처리할까요?"):
                return
        super().void_question()

    def _flash_top(self, text: str, color: str) -> None:
        if not hasattr(self, "top_status"):
            return
        self.top_status.configure(text=f"●  {text}", text_color=color)
        self.after(2200, lambda: self._refresh_active_page(force=True) if not self._closing else None)

    # ---------- onboarding ----------
    def show_onboarding(self) -> None:
        win = ctk.CTkToplevel(self)
        win.title("SOOP Quiz Studio 시작하기")
        win.geometry("820x590")
        win.configure(fg_color=BG); win.transient(self); win.grab_set(); win.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(win, text="처음이어도 4단계면 끝납니다", font=(FONT, 30, "bold"), text_color=TEXT, anchor="w").grid(row=0, column=0, padx=34, pady=(30, 5), sticky="ew")
        ctk.CTkLabel(win, text="설치할 것도, 명령어를 입력할 것도 없습니다. 방송 중에는 큰 버튼 하나만 따라가면 됩니다.", font=(FONT, 14), text_color=MUTED, anchor="w").grid(row=1, column=0, padx=34, pady=(0, 16), sticky="ew")
        steps = [
            ("1", "방송 연결", "SOOP 방송국 ID를 입력하고 ‘방송 연결’을 누릅니다."),
            ("2", "문제 준비", "문제 편집에서 문제·정답·시간을 설정합니다. 고급 규칙은 필요할 때만 사용하세요."),
            ("3", "레이어 등록", "퀴즈/TOP10/TOP3 URL을 프릭샷 또는 OBS 브라우저 소스에 붙여 넣습니다."),
            ("4", "LIVE MODE", "참가 모집을 시작하면 LIVE MODE가 자동으로 켜지고 편집/설정을 잠가 실수를 줄입니다."),
        ]
        for i, (no, title, desc) in enumerate(steps, start=2):
            card = ctk.CTkFrame(win, corner_radius=15, fg_color=PANEL, border_width=1, border_color=LINE)
            card.grid(row=i, column=0, padx=34, pady=6, sticky="ew"); card.grid_columnconfigure(1, weight=1)
            badge = ctk.CTkLabel(card, text=no, width=42, height=42, corner_radius=12, fg_color=ACCENT, text_color="#FFFFFF", font=(FONT, 17, "bold"))
            badge.grid(row=0, column=0, padx=14, pady=12)
            wrap = ctk.CTkFrame(card, fg_color="transparent"); wrap.grid(row=0, column=1, padx=(0, 16), pady=10, sticky="ew")
            ctk.CTkLabel(wrap, text=title, font=(FONT, 15, "bold"), text_color=TEXT, anchor="w").pack(fill="x")
            ctk.CTkLabel(wrap, text=desc, font=(FONT, 12), text_color=MUTED, justify="left", anchor="w", wraplength=670).pack(fill="x", pady=(3, 0))
        def done() -> None:
            self.settings["onboarding_done_v7"] = True; self._save_settings(); win.destroy()
        ctk.CTkButton(win, text="방송 준비 시작", height=52, corner_radius=13, fg_color=ACCENT, hover_color=ACCENT_HOVER, font=(FONT, 15, "bold"), command=done).grid(row=6, column=0, padx=34, pady=(16, 28), sticky="ew")


def _single_instance() -> bool:
    if sys.platform != "win32":
        return True
    try:
        kernel = ctypes.windll.kernel32
        handle = kernel.CreateMutexW(None, False, "SOOPQuizStudio-v0.7-single-instance")
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
    QuizAppV7().mainloop()


if __name__ == "__main__":
    main()
