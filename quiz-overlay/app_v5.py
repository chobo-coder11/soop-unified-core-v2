from __future__ import annotations

import ctypes
import os
import sys
import time
import urllib.request
import webbrowser
from typing import Optional

import customtkinter as ctk
from tkinter import messagebox

from app_v3 import ACCENT, BG, DANGER, FONT, GOOD, LINE, MUTED, PANEL, PANEL_2, TEXT
from app_v4 import QuizAppV4
from common import APP_NAME, APP_VERSION, SESSION_FILE, SETTINGS_FILE, app_data_dir, safe_float, safe_int
from core_runtime import BundledCoreRuntime
from overlay_server_v5 import OverlayServerV5
from quiz_engine_v5 import QuizEngineV5
from soop_client_v5 import SoopChatClientV5


class QuizAppV5(QuizAppV4):
    """v0.5 productized broadcast console.

    Normal broadcasting stays one-button driven. Advanced rules, adjudication,
    recovery and diagnostics are deliberately tucked away from the main flow.
    """

    def __init__(self) -> None:
        self._recovery_last_write = 0.0
        self._recovery_signature = None
        self.settings = self._load_json(SETTINGS_FILE, {})
        appearance = str(self.settings.get("appearance", "dark")).lower()
        ctk.set_appearance_mode({"light": "Light", "system": "System"}.get(appearance, "Dark"))
        ctk.set_default_color_theme("blue")
        ctk.CTk.__init__(self)
        self.title(f"{APP_NAME} · {APP_VERSION}")
        self.geometry("1460x920")
        self.minsize(1180, 760)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.engine = QuizEngineV5()
        self.runtime = BundledCoreRuntime()
        self.client = SoopChatClientV5(self.engine, self._socket_status)
        self.overlay = OverlayServerV5(self.engine)
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

    # ---------- broadcast console ----------
    def _build_run_page(self) -> ctk.CTkFrame:
        page = super()._build_run_page()
        ops = ctk.CTkFrame(page, corner_radius=13, fg_color=PANEL, border_width=1, border_color=LINE)
        ops.grid(row=3, column=0, sticky="ew", padx=26, pady=(0, 18))
        ops.grid_columnconfigure(4, weight=1)
        ctk.CTkLabel(ops, text="운영 도구", font=(FONT, 10, "bold"), text_color=MUTED).grid(row=0, column=0, padx=(13, 8), pady=9)
        ctk.CTkButton(ops, text="문제 무효", width=84, height=30, corner_radius=8, fg_color=PANEL_2, hover_color=LINE, text_color=TEXT, command=self.void_question).grid(row=0, column=1, padx=4, pady=6)
        ctk.CTkButton(ops, text="수동 판정", width=84, height=30, corner_radius=8, fg_color=PANEL_2, hover_color=LINE, text_color=TEXT, command=self.open_adjudication).grid(row=0, column=2, padx=4, pady=6)
        ctk.CTkButton(ops, text="점수·탈락 관리", width=112, height=30, corner_radius=8, fg_color=PANEL_2, hover_color=LINE, text_color=TEXT, command=self.open_participant_ops).grid(row=0, column=3, padx=4, pady=6)
        self.pipeline_label = ctk.CTkLabel(ops, text="수집 파이프라인 확인 중", font=(FONT, 10), text_color=MUTED, anchor="e")
        self.pipeline_label.grid(row=0, column=4, padx=(12, 13), pady=9, sticky="e")
        return page

    def _render_run_state(self) -> None:
        super()._render_run_state()
        if hasattr(self, "pipeline_label"):
            d = self.client.diagnostics()
            q = d.get("queueDepth", 0)
            drops = d.get("queueDrops", 0)
            if self.engine.practice_mode:
                text, color = "연습 모드 · 판정 엔진 정상", "#9B7CFF"
            elif d.get("subscribed") and d.get("workerAlive") and drops == 0:
                text, color = f"수집 정상 · queue {q} · seq {d.get('lastEventSeq', 0):,}", GOOD
            elif drops:
                text, color = f"수집 경고 · 누락 {drops}건", DANGER
            else:
                text, color = f"{d.get('status', '연결 확인 중')}", MUTED
            self.pipeline_label.configure(text=text, text_color=color)

    def void_question(self) -> None:
        if not self.engine.void_current_question():
            messagebox.showinfo("문제 무효", "답변 마감 후 또는 정답 공개 직후에만 문제를 무효 처리할 수 있습니다.")

    def open_adjudication(self) -> None:
        win = ctk.CTkToplevel(self)
        win.title("수동 답변 판정")
        win.geometry("680x560")
        win.transient(self); win.grab_set(); win.grid_columnconfigure(0, weight=1); win.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(win, text="수동 답변 판정", font=(FONT, 20, "bold"), anchor="w").grid(row=0, column=0, padx=20, pady=(18, 3), sticky="ew")
        ctk.CTkLabel(win, text="정답 공개 전, 예외 답안을 진행자가 직접 정답/오답 처리할 수 있습니다.", font=(FONT, 10), text_color=MUTED, anchor="w").grid(row=1, column=0, padx=20, pady=(0, 8), sticky="ew")
        box = ctk.CTkTextbox(win, font=(FONT, 11)); box.grid(row=2, column=0, padx=20, pady=8, sticky="nsew")
        rows = self.engine.answer_feed(80)
        for r in rows:
            box.insert("end", f"{r['display']}  · {r['answer']}  · {'정답' if r['correct'] else '오답'}\n")
        box.configure(state="disabled")
        controls = ctk.CTkFrame(win, fg_color="transparent"); controls.grid(row=3, column=0, padx=20, pady=(8, 18), sticky="ew"); controls.grid_columnconfigure(0, weight=1)
        uid = ctk.CTkEntry(controls, placeholder_text="판정할 사용자 ID"); uid.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        ctk.CTkButton(controls, text="정답 처리", width=90, fg_color=GOOD, hover_color="#279A68", command=lambda: self._adjudicate_and_close(win, uid.get(), True)).grid(row=0, column=1, padx=3)
        ctk.CTkButton(controls, text="오답 처리", width=90, fg_color=DANGER, hover_color="#C94552", command=lambda: self._adjudicate_and_close(win, uid.get(), False)).grid(row=0, column=2, padx=(3, 0))

    def _adjudicate_and_close(self, win, uid: str, correct: bool) -> None:
        if self.engine.adjudicate_answer(uid.strip(), correct):
            win.destroy()
        else:
            messagebox.showinfo("판정 불가", "해당 ID의 현재 문제 답변을 찾지 못했거나 판정 가능한 단계가 아닙니다.", parent=win)

    def open_participant_ops(self) -> None:
        win = ctk.CTkToplevel(self)
        win.title("점수 · 탈락 관리")
        win.geometry("650x390")
        win.transient(self); win.grab_set(); win.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(win, text="점수 · 탈락 관리", font=(FONT, 20, "bold"), anchor="w").grid(row=0, column=0, padx=20, pady=(18, 4), sticky="ew")
        ctk.CTkLabel(win, text="운영 실수 보정용입니다. 변경 내용은 운영 로그에 남습니다.", font=(FONT, 10), text_color=MUTED, anchor="w").grid(row=1, column=0, padx=20, pady=(0, 14), sticky="ew")
        frame = ctk.CTkFrame(win, corner_radius=14, fg_color=PANEL_2); frame.grid(row=2, column=0, padx=20, pady=6, sticky="ew"); frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(frame, text="사용자 ID", font=(FONT, 10, "bold")).grid(row=0, column=0, padx=12, pady=9, sticky="w")
        uid = ctk.CTkEntry(frame); uid.grid(row=0, column=1, padx=12, pady=7, sticky="ew")
        ctk.CTkLabel(frame, text="점수 증감", font=(FONT, 10, "bold")).grid(row=1, column=0, padx=12, pady=9, sticky="w")
        delta = ctk.CTkEntry(frame, placeholder_text="예: 100 또는 -100"); delta.grid(row=1, column=1, padx=12, pady=7, sticky="ew")
        ctk.CTkLabel(frame, text="사유", font=(FONT, 10, "bold")).grid(row=2, column=0, padx=12, pady=9, sticky="w")
        reason = ctk.CTkEntry(frame, placeholder_text="운영 보정"); reason.grid(row=2, column=1, padx=12, pady=7, sticky="ew")
        actions = ctk.CTkFrame(win, fg_color="transparent"); actions.grid(row=3, column=0, padx=20, pady=(10, 18), sticky="ew")
        def adjust():
            if self.engine.manual_score_adjust(uid.get().strip(), safe_int(delta.get(), 0), reason.get().strip() or "운영 보정"): win.destroy()
            else: messagebox.showinfo("확인", "해당 참가자를 찾지 못했습니다.", parent=win)
        ctk.CTkButton(actions, text="점수 반영", command=adjust).pack(side="left", padx=(0, 5))
        ctk.CTkButton(actions, text="탈락", fg_color=DANGER, hover_color="#C94552", command=lambda: self._participant_state_and_close(win, uid.get(), True)).pack(side="left", padx=5)
        ctk.CTkButton(actions, text="부활", fg_color=PANEL_2, hover_color=LINE, text_color=TEXT, command=lambda: self._participant_state_and_close(win, uid.get(), False)).pack(side="left", padx=5)

    def _participant_state_and_close(self, win, uid: str, eliminated: bool) -> None:
        if self.engine.set_participant_eliminated(uid.strip(), eliminated): win.destroy()
        else: messagebox.showinfo("확인", "해당 참가자를 찾지 못했습니다.", parent=win)

    # ---------- advanced question rules ----------
    def _build_editor_page(self) -> ctk.CTkFrame:
        page = super()._build_editor_page()
        try:
            head = page.grid_slaves(row=0, column=0)[0]
            ctk.CTkButton(head, text="고급 규칙", width=100, height=32, fg_color=PANEL_2, hover_color=LINE, text_color=TEXT, command=self.open_advanced_question_rules).pack(side="right", padx=(8, 0), pady=(0, 4))
        except Exception:
            pass
        return page

    def open_advanced_question_rules(self) -> None:
        if not self.quiz_sets.get(self.active_set_name): return
        q = self.quiz_sets[self.active_set_name][self._current_editor_index()]
        win = ctk.CTkToplevel(self); win.title("현재 문제 · 고급 규칙"); win.geometry("650x590"); win.transient(self); win.grab_set(); win.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(win, text="고급 규칙", font=(FONT, 21, "bold"), anchor="w").grid(row=0, column=0, columnspan=2, padx=22, pady=(20, 4), sticky="ew")
        ctk.CTkLabel(win, text="기본 퀴즈는 이 설정을 건드리지 않아도 됩니다.", font=(FONT, 10), text_color=MUTED, anchor="w").grid(row=1, column=0, columnspan=2, padx=22, pady=(0, 14), sticky="ew")
        def label(row, text): ctk.CTkLabel(win, text=text, font=(FONT, 10, "bold"), text_color=MUTED).grid(row=row, column=0, padx=(22, 10), pady=8, sticky="w")
        label(2,"배점 배수"); mult=ctk.StringVar(value=str(q.score_multiplier)); ctk.CTkOptionMenu(win, variable=mult, values=["1.0","1.5","2.0","3.0","5.0"]).grid(row=2,column=1,padx=(0,22),pady=7,sticky="ew")
        label(3,"탈락 규칙"); elim=ctk.StringVar(value={"none":"탈락 없음","wrong":"오답자 탈락","first_n":"선착순 N명만 생존"}.get(q.elimination_mode,"탈락 없음")); ctk.CTkOptionMenu(win,variable=elim,values=["탈락 없음","오답자 탈락","선착순 N명만 생존"]).grid(row=3,column=1,padx=(0,22),pady=7,sticky="ew")
        label(4,"숫자 판정"); num=ctk.StringVar(value="가까운 사람" if q.number_mode=="closest" else "정확히 일치"); ctk.CTkOptionMenu(win,variable=num,values=["정확히 일치","가까운 사람"]).grid(row=4,column=1,padx=(0,22),pady=7,sticky="ew")
        label(5,"근접 정답 인원"); closest=ctk.StringVar(value=str(q.closest_count)); ctk.CTkEntry(win,textvariable=closest).grid(row=5,column=1,padx=(0,22),pady=7,sticky="ew")
        label(6,"숫자 허용 오차"); tol=ctk.StringVar(value=str(q.number_tolerance)); ctk.CTkEntry(win,textvariable=tol).grid(row=6,column=1,padx=(0,22),pady=7,sticky="ew")
        allow_elim=ctk.BooleanVar(value=q.allow_eliminated_answers); ctk.CTkSwitch(win,text="탈락자도 이 문제에 답변 허용",variable=allow_elim).grid(row=7,column=0,columnspan=2,padx=22,pady=10,sticky="w")
        label(8,"진행자 메모"); note=ctk.CTkTextbox(win,height=105,corner_radius=10,fg_color=PANEL_2); note.grid(row=8,column=1,padx=(0,22),pady=7,sticky="ew"); note.insert("1.0",q.note)
        def save():
            q.score_multiplier=max(0.0,safe_float(mult.get(),1.0)); q.elimination_mode={"오답자 탈락":"wrong","선착순 N명만 생존":"first_n"}.get(elim.get(),"none"); q.number_mode="closest" if num.get()=="가까운 사람" else "exact"; q.closest_count=max(1,safe_int(closest.get(),3)); q.number_tolerance=max(0.0,safe_float(tol.get(),0)); q.allow_eliminated_answers=allow_elim.get(); q.note=note.get("1.0","end").strip()[:500]; self._save_quiz_sets(); self.engine.set_questions(self.quiz_sets[self.active_set_name]); win.destroy()
        ctk.CTkButton(win,text="고급 규칙 저장",height=44,command=save).grid(row=9,column=0,columnspan=2,padx=22,pady=(15,22),sticky="ew")

    # ---------- overlays ----------
    def _build_overlay_page(self) -> ctk.CTkFrame:
        page, body = self._page("방송 레이어", "각 URL을 프릭샷/OBS 브라우저 소스로 독립 배치할 수 있습니다.")
        for i in range(2): body.grid_columnconfigure(i, weight=1)
        self._overlay_card(body, 0, "메인 퀴즈", self.overlay.quiz_url, "문제 · START · 마감 · 정답 공개")
        self._overlay_card(body, 1, "TOP 10", self.overlay.rank_url, "정답/점수/연속정답 순위")
        self._overlay_card_row(body, 1, 0, "TOP 3", self.overlay.top3_url, "작은 포디움/상단 배치용")
        self._overlay_card_row(body, 1, 1, "진행 상태", self.overlay.status_url, "현재 단계와 참가/답변 수")
        style = ctk.CTkFrame(body, corner_radius=16, fg_color=PANEL, border_width=1, border_color=LINE); style.grid(row=2,column=0,columnspan=2,sticky="ew",pady=(12,0)); style.grid_columnconfigure(1,weight=1)
        ctk.CTkLabel(style,text="레이어 디자인",font=(FONT,13,"bold"),text_color=TEXT).grid(row=0,column=0,padx=16,pady=(14,8),sticky="w")
        self.overlay_style_var=ctk.StringVar(value={"game":"Game Show","neon":"Neon","minimal":"Minimal"}.get(self.engine.visual.get("style"),"Clean")); ctk.CTkSegmentedButton(style,values=["Clean","Game Show","Neon","Minimal"],variable=self.overlay_style_var,command=self._save_overlay_visual_v5).grid(row=0,column=1,padx=16,pady=(12,7),sticky="e")
        self.overlay_theme_var=ctk.StringVar(value="라이트" if self.engine.visual.get("theme")=="light" else "다크"); ctk.CTkSegmentedButton(style,values=["다크","라이트"],variable=self.overlay_theme_var,command=self._save_overlay_visual_v5).grid(row=1,column=0,padx=16,pady=7,sticky="w")
        self.accent_var=ctk.StringVar(value={"#ffb329":"골드","#42ca8a":"그린","#8b6cff":"퍼플"}.get(self.engine.visual.get("accent"),"블루")); ctk.CTkSegmentedButton(style,values=["블루","퍼플","골드","그린"],variable=self.accent_var,command=self._save_overlay_visual_v5).grid(row=1,column=1,padx=16,pady=7,sticky="e")
        self.motion_var=ctk.BooleanVar(value=bool(self.engine.visual.get("motion",True))); self.fastest_var=ctk.BooleanVar(value=bool(self.engine.visual.get("showFastest",True))); self.compact_var=ctk.BooleanVar(value=bool(self.engine.visual.get("compactRanking",False)))
        row=ctk.CTkFrame(style,fg_color="transparent"); row.grid(row=2,column=0,columnspan=2,padx=16,pady=(6,14),sticky="ew")
        ctk.CTkSwitch(row,text="애니메이션",variable=self.motion_var,command=self._save_overlay_visual_v5).pack(side="left",padx=(0,18)); ctk.CTkSwitch(row,text="선착순 3명 표시",variable=self.fastest_var,command=self._save_overlay_visual_v5).pack(side="left",padx=18); ctk.CTkSwitch(row,text="TOP10 컴팩트",variable=self.compact_var,command=self._save_overlay_visual_v5).pack(side="left",padx=18)
        return page

    def _overlay_card_row(self,parent,row,col,title,url,sub):
        card=ctk.CTkFrame(parent,corner_radius=16,fg_color=PANEL,border_width=1,border_color=LINE); card.grid(row=row,column=col,padx=(0 if col==0 else 6,6 if col==0 else 0),pady=(12,0),sticky="nsew")
        ctk.CTkLabel(card,text=title,font=(FONT,15,"bold"),text_color=TEXT,anchor="w").pack(fill="x",padx=16,pady=(15,2)); ctk.CTkLabel(card,text=sub,font=(FONT,10),text_color=MUTED,anchor="w").pack(fill="x",padx=16)
        entry=ctk.CTkEntry(card,height=36,border_color=LINE); entry.pack(fill="x",padx=16,pady=(12,7)); entry.insert(0,url); entry.configure(state="readonly")
        actions=ctk.CTkFrame(card,fg_color="transparent"); actions.pack(fill="x",padx=16,pady=(0,14)); ctk.CTkButton(actions,text="URL 복사",height=33,command=lambda u=url:self.copy_url(u)).pack(side="left",fill="x",expand=True,padx=(0,4)); ctk.CTkButton(actions,text="미리보기",height=33,fg_color=PANEL_2,hover_color=LINE,text_color=TEXT,command=lambda u=url:webbrowser.open(u)).pack(side="left",fill="x",expand=True,padx=(4,0))

    def _save_overlay_visual_v5(self,*_args):
        theme="light" if self.overlay_theme_var.get()=="라이트" else "dark"; style={"Game Show":"game","Neon":"neon","Minimal":"minimal"}.get(self.overlay_style_var.get(),"clean"); accent={"퍼플":"#8b6cff","골드":"#ffb329","그린":"#42ca8a"}.get(self.accent_var.get(),"#5b7cff")
        self.engine.set_visual(theme=theme,motion=self.motion_var.get(),compact_ranking=self.compact_var.get(),show_fastest=self.fastest_var.get())
        with self.engine.lock: self.engine.visual["style"]=style; self.engine.visual["accent"]=accent; self.engine._touch()
        self.settings.update({"overlay_theme":theme,"overlay_motion":self.motion_var.get(),"compact_ranking":self.compact_var.get(),"show_fastest":self.fastest_var.get(),"overlay_style":style,"overlay_accent":accent}); self._save_settings()

    # ---------- settings / diagnostics ----------
    def _build_settings_page(self) -> ctk.CTkFrame:
        page = super()._build_settings_page()
        try:
            body = page.grid_slaves(row=1, column=0)[0]
            extra=ctk.CTkFrame(body,corner_radius=16,fg_color=PANEL,border_width=1,border_color=LINE); extra.grid(row=1,column=0,columnspan=2,sticky="ew",pady=(12,0)); extra.grid_columnconfigure(1,weight=1)
            ctk.CTkLabel(extra,text="방송 운영",font=(FONT,13,"bold"),text_color=TEXT).grid(row=0,column=0,padx=16,pady=(14,8),sticky="w")
            self.midjoin_var=ctk.BooleanVar(value=self.engine.allow_mid_join); ctk.CTkSwitch(extra,text="문제 사이 중도 참가 허용",variable=self.midjoin_var,command=self._save_v5_ops).grid(row=1,column=0,padx=16,pady=(4,14),sticky="w")
            ctk.CTkLabel(extra,text="중도 참가자는 답변 접수 중에는 들어오지 않고 문제 사이에만 등록됩니다.",font=(FONT,9),text_color=MUTED,anchor="e").grid(row=1,column=1,padx=16,pady=(4,14),sticky="e")
        except Exception: pass
        return page

    def _save_v5_ops(self):
        enabled=self.midjoin_var.get(); self.engine.set_allow_mid_join(enabled); self.settings["allow_mid_join"]=enabled; self._save_settings()

    def _render_diag(self) -> None:
        if not hasattr(self,"diag_label"): return
        d=self.client.diagnostics(); age="없음" if d.get("lastEventAgeSec") is None else f"{d['lastEventAgeSec']:.1f}초 전"; pong="없음" if d.get("lastPongAgeSec") is None else f"{d['lastPongAgeSec']:.1f}초 전"
        text=(f"앱 버전: {APP_VERSION}\n내부 엔진: {self.runtime.status}\nWebSocket: {d.get('health')} · protocol {d.get('protocol') or '-'} · 구독 {'정상' if d.get('subscribed') else '대기'}\n수집 파이프라인: {d.get('pipelineHealth')} · worker {'정상' if d.get('workerAlive') else '중단'} · queue {d.get('queueDepth',0)}/{d.get('queuePeak',0)} · drop {d.get('queueDrops',0)}\n수신 이벤트: {d.get('eventCount',0):,} · 처리 이벤트: {d.get('processedEventCount',0):,} · 마지막 이벤트 {age}\nheartbeat: ping {d.get('pingCount',0)} / pong {d.get('pongCount',0)} · 마지막 pong {pong}\n현재 seq {d.get('currentSeq',0):,} · 마지막 event seq {d.get('lastEventSeq',0):,} · 최근 resume replay {d.get('lastResumeReplayed',0)}\n재연결 {d.get('reconnectCount',0)} · gap {d.get('gapCount',0)} · resume 불가 {d.get('resumeUnavailableCount',0)}\n참가자 {len(self.engine.participants):,} · 생존 {sum(1 for p in self.engine.participants.values() if not p.eliminated):,} · 참가자 채팅 {self.engine.participant_chat_total:,}\n레이어 서버: 127.0.0.1:{self.overlay.port} · {'정상' if self.overlay.is_healthy() else '확인 필요'}\n데이터 위치: {app_data_dir()}")
        if d.get("lastError"): text += f"\n최근 오류: {d['lastError']}"
        if text!=self._last_diag: self.diag_label.configure(text=text); self._last_diag=text

    # ---------- watchdog / recovery ----------
    def _checkpoint_tick(self) -> None:
        if self._closing: return
        try:
            if self.engine.participants or self.engine.state not in {"DISCONNECTED","READY"}: self._save_recovery()
        finally:
            self.after(10000,self._checkpoint_tick)

    def _watchdog_tick(self) -> None:
        if self._closing: return
        try:
            proc=self.runtime.process
            if proc is not None and proc.poll() is not None and not self._core_restart_pending:
                self.runtime.ready=False; self.runtime.status="내부 엔진 자동 복구 중"; self._core_restart_pending=True; self._watchdog_failures+=1
                def done(err):
                    self._core_restart_pending=False; self._runtime_finished(err)
                self.runtime.start_async(lambda err:self.after(0,lambda:done(err)))
            if not self.overlay.is_healthy():
                try: self.overlay.start()
                except Exception: pass
        finally:
            self.after(2500,self._watchdog_tick)

    def _ui_tick(self) -> None:
        try:
            version=self.engine.state_version
            if version!=self._last_ui_version:
                self._last_ui_version=version; self._refresh_active_page(); self._save_recovery()
            chat_version=self.engine.chat_version
            if chat_version!=self._last_chat_version:
                self._last_chat_version=chat_version
                if self._active_page=="채팅": self._render_chat_page()
                elif self._active_page=="진행" and "진행" in self._pages: self._render_run_state()
            d=self.client.diagnostics()
            if self.engine.practice_mode: self.top_status.configure(text="●  연습 모드",text_color="#9B7CFF")
            elif d.get("subscribed") and d.get("workerAlive") and not d.get("queueDrops"): self.top_status.configure(text=f"●  {self.engine.streamer_id} · 실시간 수집 정상",text_color=GOOD)
            elif d.get("threadAlive"): self.top_status.configure(text=f"●  {d.get('status')}",text_color=MUTED)
            elif self.runtime.ready and not self._runtime_error: self.top_status.configure(text="●  방송 엔진 준비 완료",text_color=MUTED)
            if self._active_page=="설정": self._render_diag()
        finally:
            self.after(250,self._ui_tick)

    def on_close(self) -> None:
        self._closing=True
        self._save_recovery()
        try: self.client.shutdown()
        except Exception: pass
        try: self.overlay.stop()
        except Exception: pass
        try: self.runtime.stop()
        except Exception: pass
        self.destroy()


def _single_instance() -> bool:
    if sys.platform != "win32": return True
    try:
        kernel=ctypes.windll.kernel32
        handle=kernel.CreateMutexW(None,False,"SOOPQuizOverlay-v0.5-single-instance")
        if not handle: return True
        return kernel.GetLastError()!=183
    except Exception:
        return True


def main() -> None:
    if not _single_instance():
        try: ctypes.windll.user32.MessageBoxW(0,"SOOP Quiz Overlay가 이미 실행 중입니다.","SOOP Quiz Overlay",0x40)
        except Exception: pass
        return
    QuizAppV5().mainloop()


if __name__ == "__main__": main()
