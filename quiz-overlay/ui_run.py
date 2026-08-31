from __future__ import annotations

import json
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox

from common import SETTINGS_FILE

class RunMixin:
    def build_run_tab(self) -> None:
        left = ttk.Frame(self.tab_run)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        right = ttk.Frame(self.tab_run, width=330)
        right.pack(side="right", fill="y")

        conn = ttk.LabelFrame(left, text="방송 연결", padding=10)
        conn.pack(fill="x")
        ttk.Label(conn, text="Unified Core WS").grid(row=0, column=0, sticky="w")
        self.ws_var = tk.StringVar(value=self.settings.get("ws", "ws://127.0.0.1:8080/v1/ws"))
        ttk.Entry(conn, textvariable=self.ws_var, width=42).grid(row=0, column=1, padx=6, sticky="ew")
        ttk.Label(conn, text="스트리머 ID").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.streamer_var = tk.StringVar(value=self.settings.get("streamer", ""))
        ttk.Entry(conn, textvariable=self.streamer_var, width=24).grid(row=1, column=1, padx=6, pady=(6, 0), sticky="w")
        self.connect_btn = ttk.Button(conn, text="연결", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=2, rowspan=2, padx=(6, 0), sticky="ns")
        conn.columnconfigure(1, weight=1)

        setbox = ttk.LabelFrame(left, text="퀴즈", padding=10)
        setbox.pack(fill="x", pady=(10, 0))
        self.set_var = tk.StringVar(value=self.active_set_name)
        self.set_combo = ttk.Combobox(setbox, textvariable=self.set_var, values=list(self.quiz_sets), state="readonly")
        self.set_combo.pack(side="left", fill="x", expand=True)
        self.set_combo.bind("<<ComboboxSelected>>", lambda e: self.load_active_set())
        ttk.Button(setbox, text="문제 편집", command=lambda: self.tabs.select(self.tab_edit)).pack(side="left", padx=(8, 0))

        statebox = ttk.LabelFrame(left, text="현재 진행", padding=16)
        statebox.pack(fill="both", expand=True, pady=(10, 0))
        self.stage_var = tk.StringVar(value="연결 대기")
        ttk.Label(statebox, textvariable=self.stage_var, font=("Malgun Gothic", 20, "bold")).pack(anchor="w")
        self.question_var = tk.StringVar(value="")
        ttk.Label(statebox, textvariable=self.question_var, font=("Malgun Gothic", 12), wraplength=700).pack(anchor="w", pady=(10, 16))
        stats = ttk.Frame(statebox)
        stats.pack(fill="x")
        self.part_var = tk.StringVar(value="참가자 0")
        self.ans_var = tk.StringVar(value="답변 0")
        self.cor_var = tk.StringVar(value="정답 0")
        for v in (self.part_var, self.ans_var, self.cor_var):
            ttk.Label(stats, textvariable=v, font=("Malgun Gothic", 11, "bold")).pack(side="left", padx=(0, 24))
        self.primary_btn = ttk.Button(statebox, text="참가 모집 시작", command=self.primary_action)
        self.primary_btn.pack(fill="x", ipady=16, pady=(26, 8))
        secondary = ttk.Frame(statebox)
        secondary.pack(fill="x")
        ttk.Button(secondary, text="답변 강제 마감", command=lambda: self.engine.close_answers(False)).pack(side="left")
        ttk.Button(secondary, text="TOP10 레이어 열기", command=lambda: webbrowser.open(self.rank_url())).pack(side="left", padx=6)
        ttk.Button(secondary, text="세션 초기화", command=self.reset_session).pack(side="right")

        rank = ttk.LabelFrame(right, text="TOP10", padding=10)
        rank.pack(fill="x")
        ttk.Label(rank, text="순위 기준").pack(anchor="w")
        self.rank_mode_var = tk.StringVar(value="맞힌 개수")
        rc = ttk.Combobox(rank, textvariable=self.rank_mode_var, values=["맞힌 개수", "점수", "연속 정답"], state="readonly")
        rc.pack(fill="x", pady=(4, 8))
        rc.bind("<<ComboboxSelected>>", lambda e: self.apply_rank_mode())
        self.rank_text = tk.Text(rank, width=36, height=18, state="disabled", font=("Consolas", 10))
        self.rank_text.pack(fill="both", expand=True)

        logbox = ttk.LabelFrame(right, text="상태 로그", padding=8)
        logbox.pack(fill="both", expand=True, pady=(10, 0))
        self.log_text = tk.Text(logbox, width=36, height=14, state="disabled", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)

    def build_layer_tab(self) -> None:
        box = ttk.LabelFrame(self.tab_layer, text="프릭샷 브라우저 레이어", padding=16)
        box.pack(fill="x")
        ttk.Label(box, text="메인 퀴즈 레이어").grid(row=0, column=0, sticky="w")
        self.quiz_url_var = tk.StringVar(value=self.quiz_url())
        ttk.Entry(box, textvariable=self.quiz_url_var, state="readonly").grid(row=1, column=0, sticky="ew", pady=(4, 10))
        ttk.Button(box, text="미리보기", command=lambda: webbrowser.open(self.quiz_url())).grid(row=1, column=1, padx=6)
        ttk.Button(box, text="복사", command=lambda: self.copy_text(self.quiz_url())).grid(row=1, column=2)
        ttk.Label(box, text="TOP10 순위 레이어 (별도 URL)").grid(row=2, column=0, sticky="w")
        self.rank_url_var = tk.StringVar(value=self.rank_url())
        ttk.Entry(box, textvariable=self.rank_url_var, state="readonly").grid(row=3, column=0, sticky="ew", pady=(4, 10))
        ttk.Button(box, text="미리보기", command=lambda: webbrowser.open(self.rank_url())).grid(row=3, column=1, padx=6)
        ttk.Button(box, text="복사", command=lambda: self.copy_text(self.rank_url())).grid(row=3, column=2)
        ttk.Label(box, text="프릭샷 브라우저 소스에 위 URL을 각각 등록하세요. 투명 배경이며, 프로그램 상태에 따라 자동 갱신됩니다.", wraplength=850).grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))
        box.columnconfigure(0, weight=1)

    def quiz_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/overlay/quiz"

    def rank_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/overlay/ranking"

    def copy_text(self, text: str) -> None:
        self.clipboard_clear(); self.clipboard_append(text); self.update()

    def toggle_connection(self) -> None:
        if not self.engine.connected:
            sid = self.streamer_var.get().strip()
            if not sid:
                messagebox.showwarning("입력 필요", "스트리머 SOOP ID를 입력해주세요.")
                return
            try:
                self.core.connect(self.ws_var.get().strip(), sid)
                self.settings.update({"ws": self.ws_var.get().strip(), "streamer": sid})
                self.path(SETTINGS_FILE).write_text(json.dumps(self.settings, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as e:
                messagebox.showerror("연결 실패", str(e))
        else:
            self.core.disconnect()

    def primary_action(self) -> None:
        st = self.engine.state
        ok = False
        if st == "READY": ok = self.engine.start_recruitment()
        elif st == "RECRUITING": ok = self.engine.close_recruitment()
        elif st == "LOCKED": ok = self.engine.show_question()
        elif st == "QUESTION_SHOWN": ok = self.engine.open_answers()
        elif st == "ANSWERING": ok = self.engine.close_answers(False)
        elif st == "QUESTION_CLOSED": ok = self.engine.reveal_answer()
        elif st == "ANSWER_REVEALED": ok = self.engine.next_question()
        elif st == "FINISHED": ok = self.engine.start_recruitment()
        if not ok:
            self.bell()

    def apply_rank_mode(self) -> None:
        m = self.rank_mode_var.get()
        self.engine.ranking_mode = "score" if m == "점수" else "streak" if m == "연속 정답" else "correct_count"

    def reset_session(self) -> None:
        if not messagebox.askyesno("세션 초기화", "참가자와 점수를 모두 초기화할까요? 문제는 유지됩니다."):
            return
        with self.engine.lock:
            self.engine.participants.clear(); self.engine.answers.clear(); self.engine.correct_order.clear(); self.engine.current_index = 0; self.engine._last_finalized_index = -1
            self.engine.state = "READY" if self.engine.connected else "DISCONNECTED"
            self.engine.overlay_notice = ""
        self.engine.log("세션 초기화")

    def stage_label(self, st: str) -> tuple[str, str]:
        mp = {
            "DISCONNECTED": ("연결 대기", "연결"),
            "READY": ("방송 연결됨", "참가 모집 시작"),
            "RECRUITING": ("참가 모집 중", "참가 마감"),
            "LOCKED": ("문제 준비", "문제 공개"),
            "QUESTION_SHOWN": ("문제 공개 · 답변 대기", "정답 입력 START"),
            "ANSWERING": ("답변 접수 중", "답변 마감"),
            "QUESTION_CLOSED": ("답변 마감", "정답 공개"),
            "ANSWER_REVEALED": ("정답 공개", "다음 문제"),
            "FINISHED": ("퀴즈 종료", "새 참가 모집"),
        }
        return mp.get(st, (st, "진행"))

    def refresh_ui(self) -> None:
        st = self.engine.state
        stage, btn = self.stage_label(st)
        self.stage_var.set(stage)
        can_progress = self.engine.connected or st in {"QUESTION_CLOSED", "ANSWER_REVEALED", "FINISHED"}
        self.primary_btn.configure(text=btn, state=("normal" if can_progress and st != "DISCONNECTED" else "disabled"))
        self.connect_btn.configure(text="연결 해제" if self.engine.connected else "연결")
        self.status_var.set(f"● {self.streamer_var.get().strip() or self.engine.streamer_id} 연결" if self.engine.connected else "● 연결 안 됨")
        q = self.engine.current_question
        self.question_var.set((f"Q{self.engine.current_index+1}/{len(self.engine.questions)} · {q.prompt}" if q else "문제가 없습니다"))
        self.part_var.set(f"참가자 {len(self.engine.participants)}")
        self.ans_var.set(f"답변 {len(self.engine.answers)}")
        self.cor_var.set(f"정답 {sum(1 for a in self.engine.answers.values() if a.correct)}")
        rows = self.engine.ranking(10)
        self.rank_text.configure(state="normal"); self.rank_text.delete("1.0", "end")
        for r in rows:
            val = f"{r['score']}점" if self.engine.ranking_mode == "score" else f"{r['streak']}연속" if self.engine.ranking_mode == "streak" else f"{r['correct']}개"
            self.rank_text.insert("end", f"{r['rank']:>2}. {r['display'][:22]:<22} {val}\n")
        self.rank_text.configure(state="disabled")
        self.log_text.configure(state="normal"); self.log_text.delete("1.0", "end"); self.log_text.insert("end", "\n".join(self.engine.event_log[-60:])); self.log_text.see("end"); self.log_text.configure(state="disabled")
        self.after(200, self.refresh_ui)
