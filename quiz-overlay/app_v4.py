from __future__ import annotations

import time

import customtkinter as ctk

from app_v3 import (
    ACCENT, BG, DANGER, FONT, GOOD, LINE, MUTED, PANEL, PANEL_2, TEXT,
)
from app_v31 import QuizAppV31
from common import APP_NAME, APP_VERSION, QUIZ_FILE, SESSION_FILE, SETTINGS_FILE, app_data_dir
from core_runtime import BundledCoreRuntime
from overlay_server_v3 import OverlayServerV3
from quiz_engine_v4 import QuizEngineV4
from soop_client_v4 import SoopChatClientV4


class QuizAppV4(QuizAppV31):
    """v0.4 broadcast console focused on chat visibility and connection clarity."""

    def __init__(self) -> None:
        self._recovery_last_write = 0.0
        self._recovery_signature = None
        self.settings = self._load_json(SETTINGS_FILE, {})
        appearance = str(self.settings.get("appearance", "dark")).lower()
        ctk.set_appearance_mode({"light": "Light", "system": "System"}.get(appearance, "Dark"))
        ctk.set_default_color_theme("blue")
        ctk.CTk.__init__(self)
        self.title(f"{APP_NAME} · {APP_VERSION}")
        self.geometry("1420x900")
        self.minsize(1140, 740)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.engine = QuizEngineV4()
        self.runtime = BundledCoreRuntime()
        self.client = SoopChatClientV4(self.engine, self._socket_status)
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
        self._last_chat_version = -1
        self._last_diag = ""
        self._pending_recovery = self._load_json(SESSION_FILE, {})
        self._build_shell()
        self.show_page("진행")
        self._bind_hotkeys()
        self.after(100, self._ui_tick)
        self.runtime.start_async(lambda err: self.after(0, lambda: self._runtime_finished(err)))
        if not self.settings.get("onboarding_done"):
            self.after(500, self.show_onboarding)

    def _build_shell(self) -> None:
        super()._build_shell()
        btn = ctk.CTkButton(
            self.sidebar,
            text="참가자 채팅",
            height=44,
            anchor="w",
            corner_radius=11,
            fg_color="transparent",
            hover_color=("#E0E6F0", "#1D2430"),
            text_color=TEXT,
            font=(FONT, 12, "bold"),
            command=lambda: self.show_page("채팅"),
        )
        btn.grid(row=5, column=0, padx=12, pady=3, sticky="ew")
        self.nav_buttons["채팅"] = btn

    def show_page(self, name: str) -> None:
        if name != "채팅":
            super().show_page(name)
            return
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
            self._pages[name] = self._build_chat_page()
        self._pages[name].grid(row=0, column=0, sticky="nsew")
        self._render_chat_page(force=True)

    def _build_run_page(self) -> ctk.CTkFrame:
        page = super()._build_run_page()
        footer = ctk.CTkFrame(page, corner_radius=13, fg_color=PANEL, border_width=1, border_color=LINE)
        footer.grid(row=2, column=0, sticky="ew", padx=26, pady=(0, 18))
        footer.grid_columnconfigure(1, weight=1)
        self.run_ws_status = ctk.CTkLabel(footer, text="● WebSocket 확인 중", font=(FONT, 10, "bold"), text_color=MUTED)
        self.run_ws_status.grid(row=0, column=0, padx=(13, 10), pady=9, sticky="w")
        self.run_last_chat = ctk.CTkLabel(footer, text="참가자 채팅: 아직 없음", font=(FONT, 10), text_color=MUTED, anchor="w")
        self.run_last_chat.grid(row=0, column=1, padx=8, pady=9, sticky="ew")
        ctk.CTkButton(
            footer,
            text="참가자 채팅 보기",
            width=116,
            height=30,
            corner_radius=8,
            fg_color=PANEL_2,
            hover_color=LINE,
            text_color=TEXT,
            command=lambda: self.show_page("채팅"),
        ).grid(row=0, column=2, padx=(8, 12), pady=6)
        return page

    def _build_chat_page(self) -> ctk.CTkFrame:
        page, body = self._page(
            "참가자 채팅",
            "!참여한 이용자의 채팅만 표시합니다. 비참가자 채팅은 저장하지 않으며 최근 500건만 메모리에 보관합니다.",
        )
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(2, weight=1)

        cards = ctk.CTkFrame(body, fg_color="transparent")
        cards.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        for i in range(4):
            cards.grid_columnconfigure(i, weight=1)
        self.chat_stat_part = self._stat(cards, 0, "추적 참가자")
        self.chat_stat_total = self._stat(cards, 1, "참가자 채팅")
        self.chat_stat_ws = self._stat(cards, 2, "WebSocket")
        self.chat_stat_seq = self._stat(cards, 3, "마지막 seq")

        controls = ctk.CTkFrame(body, corner_radius=14, fg_color=PANEL, border_width=1, border_color=LINE)
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        controls.grid_columnconfigure(1, weight=1)
        self.chat_mode_var = ctk.StringVar(value="전체 참가자 채팅")
        ctk.CTkOptionMenu(
            controls,
            values=["전체 참가자 채팅", "답변만", "일반 채팅만"],
            variable=self.chat_mode_var,
            width=150,
            command=lambda _v: self._render_chat_page(force=True),
        ).grid(row=0, column=0, padx=(12, 6), pady=9)
        self.chat_search_var = ctk.StringVar()
        search = ctk.CTkEntry(controls, textvariable=self.chat_search_var, placeholder_text="닉네임 · ID · 메시지 검색", height=34, border_color=LINE)
        search.grid(row=0, column=1, padx=6, pady=9, sticky="ew")
        search.bind("<KeyRelease>", lambda _e: self._render_chat_page(force=True))
        ctk.CTkButton(
            controls,
            text="화면 기록 지우기",
            width=112,
            height=34,
            fg_color=PANEL_2,
            hover_color=LINE,
            text_color=TEXT,
            command=self.engine.clear_participant_chat,
        ).grid(row=0, column=2, padx=(6, 12), pady=9)

        panel = ctk.CTkFrame(body, corner_radius=16, fg_color=PANEL, border_width=1, border_color=LINE)
        panel.grid(row=2, column=0, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)
        self.chat_summary = ctk.CTkLabel(panel, text="", font=(FONT, 10, "bold"), text_color=MUTED, anchor="w")
        self.chat_summary.grid(row=0, column=0, padx=14, pady=(11, 4), sticky="ew")
        self.participant_chat_text = ctk.CTkTextbox(panel, corner_radius=10, fg_color=PANEL_2, border_width=0, font=(FONT, 11), activate_scrollbars=True)
        self.participant_chat_text.grid(row=1, column=0, padx=10, pady=(4, 10), sticky="nsew")
        self.participant_chat_text.configure(state="disabled")
        return page

    def _render_chat_page(self, force: bool = False) -> None:
        if not hasattr(self, "participant_chat_text"):
            return
        rows = self.engine.participant_chat_feed(180)
        mode = self.chat_mode_var.get() if hasattr(self, "chat_mode_var") else "전체 참가자 채팅"
        query = self.chat_search_var.get().strip().casefold() if hasattr(self, "chat_search_var") else ""
        filtered = []
        for row in rows:
            if mode == "답변만" and not row.get("isAnswer"):
                continue
            if mode == "일반 채팅만" and row.get("isAnswer"):
                continue
            haystack = f"{row.get('display','')} {row.get('message','')}".casefold()
            if query and query not in haystack:
                continue
            filtered.append(row)

        self.participant_chat_text.configure(state="normal")
        self.participant_chat_text.delete("1.0", "end")
        if not filtered:
            self.participant_chat_text.insert("end", "아직 표시할 참가자 채팅이 없습니다.\n\n참가 모집 후 시청자가 !참여를 입력하면 그 시점부터 해당 ID의 채팅만 추적됩니다.")
        else:
            for row in filtered:
                received = str(row.get("receivedAt") or "")
                clock = received.split("T")[-1][:8] if "T" in received else "--:--:--"
                if row.get("joined"):
                    tag = "참여"
                elif row.get("cancelled"):
                    tag = "취소"
                elif row.get("isAnswer"):
                    tag = "답변"
                else:
                    tag = "채팅"
                self.participant_chat_text.insert("end", f"[{clock}] [{tag}] {row['display']}\n  {row['message']}\n\n")
        self.participant_chat_text.configure(state="disabled")

        diag = self.client.diagnostics()
        self.chat_stat_part.configure(text=f"{len(self.engine.participants):,}")
        self.chat_stat_total.configure(text=f"{self.engine.participant_chat_total:,}")
        self.chat_stat_ws.configure(text="정상" if diag["subscribed"] else "대기")
        self.chat_stat_seq.configure(text=f"{diag['lastEventSeq']:,}")
        self.chat_summary.configure(text=f"최근 {min(len(rows), 180)}건 표시 · 비참가자 채팅 미수집 · 메모리 최대 500건")

    def _render_run_state(self) -> None:
        super()._render_run_state()
        if not hasattr(self, "run_ws_status"):
            return
        diag = self.client.diagnostics()
        if self.engine.practice_mode:
            self.run_ws_status.configure(text="● 연습 모드", text_color="#9B7CFF")
        elif diag["subscribed"]:
            self.run_ws_status.configure(text="● WebSocket 구독 정상", text_color=GOOD)
        elif diag["threadAlive"]:
            self.run_ws_status.configure(text="● WebSocket 연결 중", text_color=MUTED)
        else:
            self.run_ws_status.configure(text="● WebSocket 연결 안 됨", text_color=DANGER if self.engine.connected else MUTED)
        latest = self.engine.latest_participant_chat()
        if latest:
            message = str(latest.get("message") or "").replace("\n", " ")
            if len(message) > 62:
                message = message[:59] + "..."
            self.run_last_chat.configure(text=f"최근 참가자 채팅 · {latest['display']}  {message}")
        else:
            self.run_last_chat.configure(text="참가자 채팅: 아직 없음")

    def _render_diag(self) -> None:
        if not hasattr(self, "diag_label"):
            return
        d = self.client.diagnostics()
        age = "없음" if d["lastEventAgeSec"] is None else f"{d['lastEventAgeSec']:.1f}초 전"
        text = (
            f"앱 버전: {APP_VERSION}\n"
            f"내부 엔진: {self.runtime.status}\n"
            f"WebSocket 상태: {d['health']} · {d['status']}\n"
            f"프로토콜: {d['protocol'] or '-'} · 구독: {'예' if d['subscribed'] else '아니오'}\n"
            f"수신 이벤트: {d['eventCount']:,}건 · 마지막 이벤트: {age}\n"
            f"현재 seq: {d['currentSeq']:,} · 마지막 이벤트 seq: {d['lastEventSeq']:,}\n"
            f"재연결: {d['reconnectCount']}회 · gap: {d['gapCount']}회 · resume 불가: {d['resumeUnavailableCount']}회\n"
            f"참가자 채팅 추적: {self.engine.participant_chat_total:,}건 · 메모리 보관 {len(self.engine.participant_chat_feed(500)):,}건\n"
            f"레이어 서버: 127.0.0.1:{self.overlay.port}\n"
            f"현재 단계: {self.engine.state}\n"
            f"데이터 위치: {app_data_dir()}"
        )
        if d["lastError"]:
            text += f"\n최근 WebSocket 오류: {d['lastError']}"
        if text != self._last_diag:
            self.diag_label.configure(text=text)
            self._last_diag = text

    def _refresh_active_page(self, force: bool = False) -> None:
        if self._active_page == "채팅" and "채팅" in self._pages:
            self._render_chat_page(force=force)
        else:
            super()._refresh_active_page(force=force)

    def _ui_tick(self) -> None:
        try:
            version = self.engine.state_version
            if version != self._last_ui_version:
                self._last_ui_version = version
                self._refresh_active_page()
                self._save_recovery()
            chat_version = self.engine.chat_version
            if chat_version != self._last_chat_version:
                self._last_chat_version = chat_version
                if self._active_page == "채팅":
                    self._render_chat_page()
                elif self._active_page == "진행" and "진행" in self._pages:
                    self._render_run_state()
            d = self.client.diagnostics()
            if self.engine.practice_mode:
                self.top_status.configure(text="●  연습 모드", text_color="#9B7CFF")
            elif d["subscribed"]:
                self.top_status.configure(text=f"●  {self.engine.streamer_id} 실시간 연결 정상", text_color=GOOD)
            elif d["threadAlive"]:
                self.top_status.configure(text=f"●  {d['status']}", text_color=MUTED)
            elif self.runtime.ready and not self._runtime_error:
                self.top_status.configure(text="●  방송 엔진 준비 완료", text_color=MUTED)
            if self._active_page == "설정":
                self._render_diag()
        finally:
            self.after(180, self._ui_tick)


def main() -> None:
    QuizAppV4().mainloop()


if __name__ == "__main__":
    main()
