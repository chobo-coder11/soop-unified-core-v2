from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from common import Question, safe_float, safe_int

class EditMixin:
    def build_edit_tab(self) -> None:
        left = ttk.Frame(self.tab_edit)
        left.pack(side="left", fill="y", padx=(0, 12))
        right = ttk.Frame(self.tab_edit)
        right.pack(side="left", fill="both", expand=True)

        setrow = ttk.Frame(left)
        setrow.pack(fill="x")
        ttk.Label(setrow, text="퀴즈 세트").pack(anchor="w")
        self.edit_set_var = tk.StringVar(value=self.active_set_name)
        self.edit_set_combo = ttk.Combobox(setrow, textvariable=self.edit_set_var, values=list(self.quiz_sets), state="readonly", width=24)
        self.edit_set_combo.pack(fill="x", pady=(4, 6))
        self.edit_set_combo.bind("<<ComboboxSelected>>", lambda e: self.edit_switch_set())
        b = ttk.Frame(setrow); b.pack(fill="x")
        ttk.Button(b, text="새 세트", command=self.new_set).pack(side="left")
        ttk.Button(b, text="세트 삭제", command=self.delete_set).pack(side="left", padx=4)

        self.q_list = tk.Listbox(left, width=34, height=27)
        self.q_list.pack(fill="y", pady=(10, 6))
        self.q_list.bind("<<ListboxSelect>>", lambda e: self.load_question_form())
        move = ttk.Frame(left); move.pack(fill="x")
        ttk.Button(move, text="+ 문제", command=self.add_question).pack(side="left")
        ttk.Button(move, text="삭제", command=self.delete_question).pack(side="left", padx=4)
        ttk.Button(move, text="↑", width=3, command=lambda: self.move_question(-1)).pack(side="right")
        ttk.Button(move, text="↓", width=3, command=lambda: self.move_question(1)).pack(side="right", padx=4)

        form = ttk.LabelFrame(right, text="문제 설정", padding=12)
        form.pack(fill="both", expand=True)
        self.kind_var = tk.StringVar(value="객관식")
        ttk.Label(form, text="문제 유형").grid(row=0, column=0, sticky="w")
        kind = ttk.Combobox(form, textvariable=self.kind_var, values=["객관식", "주관식", "OX", "숫자"], state="readonly", width=16)
        kind.grid(row=0, column=1, sticky="w", pady=3)
        kind.bind("<<ComboboxSelected>>", lambda e: self.update_form_help())
        ttk.Label(form, text="문제").grid(row=1, column=0, sticky="nw", pady=(8, 0))
        self.prompt_text = tk.Text(form, height=5, font=("Malgun Gothic", 11))
        self.prompt_text.grid(row=1, column=1, columnspan=3, sticky="nsew", pady=(8, 0))
        ttk.Label(form, text="보기").grid(row=2, column=0, sticky="nw", pady=(8, 0))
        self.choices_text = tk.Text(form, height=6, font=("Malgun Gothic", 10))
        self.choices_text.grid(row=2, column=1, columnspan=3, sticky="nsew", pady=(8, 0))
        ttk.Label(form, text="한 줄에 보기 하나 · 객관식에서만 사용").grid(row=3, column=1, columnspan=3, sticky="w")
        ttk.Label(form, text="정답").grid(row=4, column=0, sticky="w", pady=(8, 0))
        self.answer_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.answer_var).grid(row=4, column=1, sticky="ew", pady=(8, 0))
        ttk.Label(form, text="추가 인정 정답").grid(row=5, column=0, sticky="w", pady=(8, 0))
        self.accepted_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.accepted_var).grid(row=5, column=1, columnspan=3, sticky="ew", pady=(8, 0))
        ttk.Label(form, text="쉼표로 구분 · 주관식 전용").grid(row=6, column=1, columnspan=3, sticky="w")

        ttk.Label(form, text="제한시간(초)").grid(row=7, column=0, sticky="w", pady=(10, 0))
        self.duration_var = tk.StringVar(value="15")
        ttk.Entry(form, textvariable=self.duration_var, width=10).grid(row=7, column=1, sticky="w", pady=(10, 0))
        ttk.Label(form, text="답변 정책").grid(row=7, column=2, sticky="e", pady=(10, 0), padx=(10, 4))
        self.policy_var = tk.StringVar(value="마지막 답변 인정")
        ttk.Combobox(form, textvariable=self.policy_var, values=["마지막 답변 인정", "첫 답변만 인정"], state="readonly", width=18).grid(row=7, column=3, sticky="w", pady=(10, 0))

        ttk.Label(form, text="점수 방식").grid(row=8, column=0, sticky="w", pady=(10, 0))
        self.scoring_var = tk.StringVar(value="전체 정답자")
        ttk.Combobox(form, textvariable=self.scoring_var, values=["전체 정답자", "선착순 N명", "전체 + 선착순 보너스"], state="readonly", width=22).grid(row=8, column=1, sticky="w", pady=(10, 0))
        ttk.Label(form, text="선착순 N").grid(row=8, column=2, sticky="e", pady=(10, 0), padx=(10, 4))
        self.firstn_var = tk.StringVar(value="3")
        ttk.Entry(form, textvariable=self.firstn_var, width=8).grid(row=8, column=3, sticky="w", pady=(10, 0))
        ttk.Label(form, text="기본 점수").grid(row=9, column=0, sticky="w", pady=(8, 0))
        self.basepoints_var = tk.StringVar(value="100")
        ttk.Entry(form, textvariable=self.basepoints_var, width=10).grid(row=9, column=1, sticky="w", pady=(8, 0))
        ttk.Label(form, text="순위 점수").grid(row=9, column=2, sticky="e", pady=(8, 0), padx=(10, 4))
        self.rankpoints_var = tk.StringVar(value="300,200,100")
        ttk.Entry(form, textvariable=self.rankpoints_var).grid(row=9, column=3, sticky="ew", pady=(8, 0))

        self.auto_time_var = tk.BooleanVar(value=True)
        self.auto_quota_var = tk.BooleanVar(value=False)
        self.ignore_space_var = tk.BooleanVar(value=True)
        self.ignore_punct_var = tk.BooleanVar(value=True)
        opts = ttk.Frame(form)
        opts.grid(row=10, column=0, columnspan=4, sticky="w", pady=(12, 0))
        ttk.Checkbutton(opts, text="시간 종료 시 답변만 자동 마감", variable=self.auto_time_var).pack(side="left")
        ttk.Checkbutton(opts, text="선착순 N명 달성 시 답변만 자동 마감", variable=self.auto_quota_var).pack(side="left", padx=12)
        opts2 = ttk.Frame(form); opts2.grid(row=11, column=0, columnspan=4, sticky="w", pady=(6, 0))
        ttk.Checkbutton(opts2, text="주관식 띄어쓰기 무시", variable=self.ignore_space_var).pack(side="left")
        ttk.Checkbutton(opts2, text="주관식 특수문자 무시", variable=self.ignore_punct_var).pack(side="left", padx=12)
        ttk.Label(form, text="숫자 허용 오차").grid(row=12, column=0, sticky="w", pady=(8, 0))
        self.tolerance_var = tk.StringVar(value="0")
        ttk.Entry(form, textvariable=self.tolerance_var, width=10).grid(row=12, column=1, sticky="w", pady=(8, 0))
        self.form_help = tk.StringVar(value="객관식 정답은 보기 번호(예: 2)를 입력하세요.")
        ttk.Label(form, textvariable=self.form_help).grid(row=13, column=0, columnspan=4, sticky="w", pady=(10, 0))
        ttk.Button(form, text="문제 저장", command=self.save_question_form).grid(row=14, column=0, columnspan=4, sticky="ew", pady=(18, 0), ipady=8)
        form.columnconfigure(1, weight=1); form.columnconfigure(3, weight=1); form.rowconfigure(1, weight=1); form.rowconfigure(2, weight=1)
        self.refresh_question_list()
        if self.engine.questions:
            self.q_list.selection_set(0); self.load_question_form()

    def edit_switch_set(self) -> None:
        self.active_set_name = self.edit_set_var.get()
        self.set_var.set(self.active_set_name)
        self.engine.questions = self.quiz_sets[self.active_set_name]
        self.engine.current_index = 0
        self.refresh_question_list()

    def load_active_set(self) -> None:
        self.active_set_name = self.set_var.get()
        self.edit_set_var.set(self.active_set_name)
        self.engine.questions = self.quiz_sets[self.active_set_name]
        self.engine.current_index = 0
        self.refresh_question_list()

    def new_set(self) -> None:
        name = self.simple_prompt("새 퀴즈 세트 이름")
        if not name: return
        if name in self.quiz_sets:
            messagebox.showwarning("중복", "같은 이름의 세트가 있습니다."); return
        self.quiz_sets[name] = [Question(prompt="새 문제")]
        self.active_set_name = name
        self.edit_set_var.set(name); self.set_var.set(name)
        self.update_set_combos(); self.engine.questions = self.quiz_sets[name]; self.save_quiz_sets(); self.refresh_question_list()

    def simple_prompt(self, title: str) -> Optional[str]:
        win = tk.Toplevel(self); win.title(title); win.transient(self); win.grab_set(); val = tk.StringVar(); result = {"v": None}
        ttk.Entry(win, textvariable=val, width=36).pack(padx=14, pady=14)
        def done(): result["v"] = val.get().strip(); win.destroy()
        ttk.Button(win, text="확인", command=done).pack(pady=(0,14)); win.wait_window(); return result["v"]

    def delete_set(self) -> None:
        name = self.edit_set_var.get()
        if len(self.quiz_sets) <= 1: messagebox.showwarning("삭제 불가", "퀴즈 세트는 최소 1개 필요합니다."); return
        if not messagebox.askyesno("세트 삭제", f"'{name}' 세트를 삭제할까요?"): return
        del self.quiz_sets[name]; self.active_set_name = next(iter(self.quiz_sets)); self.edit_set_var.set(self.active_set_name); self.set_var.set(self.active_set_name); self.engine.questions = self.quiz_sets[self.active_set_name]; self.update_set_combos(); self.save_quiz_sets(); self.refresh_question_list()

    def update_set_combos(self) -> None:
        vals = list(self.quiz_sets); self.set_combo.configure(values=vals); self.edit_set_combo.configure(values=vals)

    def refresh_question_list(self) -> None:
        if not hasattr(self, "q_list"): return
        self.q_list.delete(0, "end")
        for i, q in enumerate(self.engine.questions):
            label = {"multiple":"객관식","short":"주관식","ox":"OX","number":"숫자"}.get(q.kind,q.kind)
            self.q_list.insert("end", f"Q{i+1} [{label}] {q.prompt[:22]}")

    def selected_q_index(self) -> int:
        sel = self.q_list.curselection(); return int(sel[0]) if sel else max(0, min(self.engine.current_index, len(self.engine.questions)-1))

    def add_question(self) -> None:
        self.engine.questions.append(Question(prompt="새 문제")); self.save_quiz_sets(); self.refresh_question_list(); idx=len(self.engine.questions)-1; self.q_list.selection_clear(0,"end"); self.q_list.selection_set(idx); self.load_question_form()

    def delete_question(self) -> None:
        if len(self.engine.questions)<=1: messagebox.showwarning("삭제 불가","문제는 최소 1개 필요합니다."); return
        idx=self.selected_q_index(); del self.engine.questions[idx]; self.save_quiz_sets(); self.refresh_question_list(); self.q_list.selection_set(max(0,idx-1)); self.load_question_form()

    def move_question(self, delta: int) -> None:
        idx=self.selected_q_index(); ni=idx+delta
        if ni<0 or ni>=len(self.engine.questions): return
        self.engine.questions[idx],self.engine.questions[ni]=self.engine.questions[ni],self.engine.questions[idx]; self.save_quiz_sets(); self.refresh_question_list(); self.q_list.selection_set(ni)

    def load_question_form(self) -> None:
        if not self.engine.questions: return
        q=self.engine.questions[self.selected_q_index()]
        self.kind_var.set({"multiple":"객관식","short":"주관식","ox":"OX","number":"숫자"}.get(q.kind,"객관식"))
        self.prompt_text.delete("1.0","end"); self.prompt_text.insert("1.0",q.prompt)
        self.choices_text.delete("1.0","end"); self.choices_text.insert("1.0","\n".join(q.choices))
        self.answer_var.set(q.answer); self.accepted_var.set(", ".join(q.accepted_answers)); self.duration_var.set(str(q.duration_sec)); self.policy_var.set("첫 답변만 인정" if q.answer_policy=="first" else "마지막 답변 인정")
        self.scoring_var.set("선착순 N명" if q.scoring_mode=="first_n" else "전체 + 선착순 보너스" if q.scoring_mode=="mixed" else "전체 정답자")
        self.firstn_var.set(str(q.first_n)); self.basepoints_var.set(str(q.base_points)); self.rankpoints_var.set(",".join(map(str,q.rank_points))); self.auto_time_var.set(q.auto_close_time); self.auto_quota_var.set(q.auto_close_quota); self.ignore_space_var.set(q.ignore_space); self.ignore_punct_var.set(q.ignore_punct); self.tolerance_var.set(str(q.number_tolerance)); self.update_form_help()

    def update_form_help(self) -> None:
        m={"객관식":"객관식 정답은 보기 번호(예: 2)를 입력하세요. 시청자는 !1, !2 ...","주관식":"주관식 정답과 추가 인정 정답을 설정하세요. 시청자는 !정답 서울","OX":"정답에는 O 또는 X를 입력하세요. 시청자는 !O / !X","숫자":"정답 숫자와 허용 오차를 설정하세요. 시청자는 !숫자 2500 또는 !2500"}
        self.form_help.set(m.get(self.kind_var.get(),""))

    def save_question_form(self) -> None:
        if not self.engine.questions: return
        idx=self.selected_q_index(); q=self.engine.questions[idx]
        kind={"객관식":"multiple","주관식":"short","OX":"ox","숫자":"number"}[self.kind_var.get()]
        prompt=self.prompt_text.get("1.0","end").strip(); choices=[x.strip() for x in self.choices_text.get("1.0","end").splitlines() if x.strip()][:6]
        if not prompt: messagebox.showwarning("입력 필요","문제를 입력해주세요."); return
        if kind=="multiple" and len(choices)<2: messagebox.showwarning("입력 필요","객관식 보기는 최소 2개 필요합니다."); return
        ans=self.answer_var.get().strip()
        if not ans: messagebox.showwarning("입력 필요","정답을 입력해주세요."); return
        q.kind=kind; q.prompt=prompt; q.choices=choices; q.answer=ans; q.accepted_answers=[x.strip() for x in self.accepted_var.get().split(",") if x.strip()]; q.duration_sec=max(1,min(3600,safe_int(self.duration_var.get(),15))); q.answer_policy="first" if self.policy_var.get()=="첫 답변만 인정" else "last"; q.scoring_mode="first_n" if self.scoring_var.get()=="선착순 N명" else "mixed" if self.scoring_var.get()=="전체 + 선착순 보너스" else "all"; q.first_n=max(1,min(1000,safe_int(self.firstn_var.get(),3))); q.base_points=safe_int(self.basepoints_var.get(),100); q.rank_points=[safe_int(x.strip(),0) for x in self.rankpoints_var.get().split(",") if x.strip()]; q.auto_close_time=self.auto_time_var.get(); q.auto_close_quota=self.auto_quota_var.get(); q.ignore_space=self.ignore_space_var.get(); q.ignore_punct=self.ignore_punct_var.get(); q.number_tolerance=max(0.0,safe_float(self.tolerance_var.get(),0.0)); self.quiz_sets[self.active_set_name]=self.engine.questions; self.save_quiz_sets(); self.refresh_question_list(); self.q_list.selection_set(idx); messagebox.showinfo("저장 완료","문제를 저장했습니다.")
