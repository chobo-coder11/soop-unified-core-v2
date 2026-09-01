from __future__ import annotations

import ctypes
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import customtkinter as ctk
from tkinter import filedialog, messagebox

import app_v9
from app_v8 import (
    ACCENT,
    ACCENT_HOVER,
    DANGER,
    FONT,
    GOOD,
    LINE,
    MUTED,
    PANEL,
    PANEL_2,
    PANEL_3,
    TEXT,
    WARNING,
)
from common import Question, safe_float, safe_int
from overlay_server_v10 import OverlayServerV10
from quiz_engine_v10 import QuizEngineV10, UI_VERSION


PRODUCT_NAME = "SOOP Quiz Studio"

KIND_TO_UI = {
    "multiple": "객관식",
    "ox": "OX",
    "short": "주관식",
    "number": "숫자 맞히기",
}
UI_TO_KIND = {v: k for k, v in KIND_TO_UI.items()}

SCORE_TO_UI = {
    "all": "맞힌 사람 모두 점수",
    "first_n": "빠른 사람만 점수",
    "mixed": "모두 점수 + 빠른 사람 보너스",
}
UI_TO_SCORE = {v: k for k, v in SCORE_TO_UI.items()}

POLICY_TO_UI = {
    "last": "마지막에 보낸 답으로 채점",
    "first": "처음 보낸 답만 인정",
}
UI_TO_POLICY = {v: k for k, v in POLICY_TO_UI.items()}

NUMBER_TO_UI = {
    "exact": "정답과 같으면 정답",
    "closest": "정답에 가장 가까운 사람 순",
}
UI_TO_NUMBER = {v: k for k, v in NUMBER_TO_UI.items()}

ELIM_TO_UI = {
    "none": "탈락 없음",
    "wrong": "틀린 사람 탈락",
    "first_n": "빠른 N명만 생존",
}
UI_TO_ELIM = {v: k for k, v in ELIM_TO_UI.items()}


class QuizAppV10(app_v9.QuizAppV9):
    """Streamer-first UX pass.

    The v0.9 engine/transport guarantees remain intact. v0.10 replaces the
    inherited developer-shaped question editor with a guided editor, silently
    preserves drafts during navigation, and keeps technical language out of the
    normal broadcast path.
    """

    def __init__(self) -> None:
        # QuizAppV9 resolves these names from its own module during construction.
        app_v9.QuizEngineV9 = QuizEngineV10
        app_v9.OverlayServerV9 = OverlayServerV10
        app_v9.UI_VERSION = UI_VERSION
        self._editor_loading = False
        self._editor_ready = False
        self._editor_status_after = None
        super().__init__()
        self.title(f"{PRODUCT_NAME} · v{UI_VERSION}")

    # ---------- simpler shell language ----------
    def _build_shell(self) -> None:
        super()._build_shell()
        if hasattr(self, "nav_buttons"):
            labels = {
                "진행": "방송 진행",
                "문제": "문제 만들기",
                "채팅": "참가자 채팅",
                "레이어": "방송 화면",
                "설정": "설정 · 문제 해결",
            }
            for key, text in labels.items():
                if key in self.nav_buttons:
                    self.nav_buttons[key].configure(text=text)
        if hasattr(self, "live_lock_button"):
            self.live_lock_button.configure(text="방송 중 편집 잠금", width=126)

    def show_page(self, name: str) -> None:
        if getattr(self, "_active_page", "") == "문제" and name != "문제":
            self._save_editor_draft(validate=False, refresh=False)
        super().show_page(name)

    # ---------- editor shell ----------
    def _build_editor_page(self) -> ctk.CTkFrame:
        page, body = self._page(
            "문제 만들기",
            "문제 내용과 정답만 먼저 만들면 됩니다. 어려운 설정은 필요한 경우에만 열어보세요.",
        )
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(body, corner_radius=14, fg_color=PANEL, border_width=1, border_color=LINE)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        toolbar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(toolbar, text="퀴즈", font=(FONT, 10, "bold"), text_color=MUTED).grid(
            row=0, column=0, padx=(14, 7), pady=11
        )
        self.edit_set_var = ctk.StringVar(value=self.active_set_name)
        self.edit_set_menu = ctk.CTkOptionMenu(
            toolbar,
            variable=self.edit_set_var,
            values=list(self.quiz_sets),
            height=34,
            corner_radius=9,
            command=self._change_active_set,
        )
        self.edit_set_menu.grid(row=0, column=1, padx=4, pady=9, sticky="ew")
        for col, (text, command, width) in enumerate(
            [
                ("새 퀴즈", self.new_set, 78),
                ("퀴즈 관리", self.open_set_manager, 86),
                ("파일 불러오기", self.import_quiz_file, 100),
                ("백업 저장", self.export_quiz_file, 82),
            ],
            start=2,
        ):
            ctk.CTkButton(
                toolbar,
                text=text,
                width=width,
                height=34,
                corner_radius=9,
                fg_color=PANEL_2,
                hover_color=PANEL_3,
                text_color=TEXT,
                command=command,
            ).grid(row=0, column=col, padx=(4, 14 if col == 5 else 4), pady=9)

        main = ctk.CTkFrame(body, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew")
        main.grid_columnconfigure(0, weight=0, minsize=278)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)

        # Left: real question list instead of a number dropdown + read-only textbox.
        nav = ctk.CTkFrame(main, width=278, corner_radius=15, fg_color=PANEL, border_width=1, border_color=LINE)
        nav.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        nav.grid_propagate(False)
        nav.grid_columnconfigure(0, weight=1)
        nav.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(nav, text="문제 목록", font=(FONT, 13, "bold"), text_color=TEXT, anchor="w").grid(
            row=0, column=0, padx=13, pady=(14, 1), sticky="ew"
        )
        self.editor_count_label = ctk.CTkLabel(nav, text="", font=(FONT, 9), text_color=MUTED, anchor="w")
        self.editor_count_label.grid(row=1, column=0, padx=13, pady=(0, 8), sticky="ew")
        self.question_list = ctk.CTkScrollableFrame(nav, fg_color="transparent", corner_radius=0)
        self.question_list.grid(row=2, column=0, sticky="nsew", padx=7, pady=(0, 6))
        self.question_list.grid_columnconfigure(0, weight=1)
        self.question_index_var = ctk.StringVar(value="1")
        self.question_buttons: list[ctk.CTkButton] = []

        nav_actions = ctk.CTkFrame(nav, fg_color="transparent")
        nav_actions.grid(row=3, column=0, padx=9, pady=(2, 5), sticky="ew")
        nav_actions.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            nav_actions,
            text="+ 새 문제",
            height=36,
            corner_radius=9,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            command=self.add_question,
        ).grid(row=0, column=0, columnspan=2, padx=2, pady=(0, 5), sticky="ew")
        ctk.CTkButton(
            nav_actions,
            text="복제",
            height=32,
            corner_radius=8,
            fg_color=PANEL_2,
            hover_color=PANEL_3,
            text_color=TEXT,
            command=self.duplicate_question,
        ).grid(row=1, column=0, padx=2, sticky="ew")
        ctk.CTkButton(
            nav_actions,
            text="삭제",
            height=32,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color=LINE,
            hover_color=PANEL_2,
            text_color=DANGER,
            command=self.delete_question,
        ).grid(row=1, column=1, padx=2, sticky="ew")

        order = ctk.CTkFrame(nav, fg_color="transparent")
        order.grid(row=4, column=0, padx=9, pady=(0, 10), sticky="ew")
        order.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            order, text="↑ 위로", height=29, fg_color="transparent", hover_color=PANEL_2,
            border_width=1, border_color=LINE, text_color=MUTED, command=lambda: self._move_question(-1)
        ).grid(row=0, column=0, padx=2, sticky="ew")
        ctk.CTkButton(
            order, text="↓ 아래로", height=29, fg_color="transparent", hover_color=PANEL_2,
            border_width=1, border_color=LINE, text_color=MUTED, command=lambda: self._move_question(1)
        ).grid(row=0, column=1, padx=2, sticky="ew")

        # Right: guided form. Only relevant answer fields are visible.
        form = ctk.CTkScrollableFrame(main, corner_radius=15, fg_color=PANEL, border_width=1, border_color=LINE)
        form.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        form.grid_columnconfigure(0, weight=1)

        self.editor_vars: dict[str, Any] = {}
        self.kind_var = ctk.StringVar(value="객관식")
        self.editor_vars["kind"] = self.kind_var
        self._section_title(form, 0, "1. 어떤 문제인가요?", "종류를 고르고 시청자에게 보여줄 문제를 적어주세요.")
        self.kind_segment = ctk.CTkSegmentedButton(
            form,
            values=["객관식", "OX", "주관식", "숫자 맞히기"],
            variable=self.kind_var,
            height=36,
            command=self._editor_type_changed,
        )
        self.kind_segment.grid(row=1, column=0, padx=16, pady=(4, 10), sticky="ew")
        self.prompt_box = ctk.CTkTextbox(
            form, height=104, corner_radius=10, fg_color=PANEL_2, border_width=1, border_color=LINE, font=(FONT, 12)
        )
        self.prompt_box.grid(row=2, column=0, padx=16, pady=(0, 14), sticky="ew")
        self.prompt_box.bind("<KeyRelease>", lambda _e: self._mark_editor_dirty())
        self.editor_vars["prompt"] = self.prompt_box

        self._section_title(form, 3, "2. 정답을 정해주세요", "선택한 문제 종류에 맞는 항목만 표시됩니다.")
        self.answer_area = ctk.CTkFrame(form, fg_color="transparent")
        self.answer_area.grid(row=4, column=0, padx=16, pady=(0, 14), sticky="ew")
        self.answer_area.grid_columnconfigure(0, weight=1)

        # 객관식
        self.choice_card = self._card(self.answer_area)
        self.choice_card.grid(row=0, column=0, sticky="ew")
        self.choice_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self.choice_card, text="보기", font=(FONT, 10, "bold"), text_color=TEXT, anchor="w"
        ).grid(row=0, column=0, padx=12, pady=(11, 3), sticky="ew")
        ctk.CTkLabel(
            self.choice_card, text="한 줄에 보기 하나씩 입력하세요. 최대 6개까지 사용할 수 있습니다.",
            font=(FONT, 9), text_color=MUTED, anchor="w"
        ).grid(row=1, column=0, padx=12, pady=(0, 5), sticky="ew")
        self.choices_box = ctk.CTkTextbox(
            self.choice_card, height=118, corner_radius=9, fg_color=PANEL, border_width=1, border_color=LINE, font=(FONT, 11)
        )
        self.choices_box.grid(row=2, column=0, padx=12, pady=(0, 9), sticky="ew")
        self.choices_box.bind("<KeyRelease>", self._choices_changed)
        self.editor_vars["choices"] = self.choices_box
        ctk.CTkLabel(
            self.choice_card, text="정답 보기", font=(FONT, 10, "bold"), text_color=TEXT, anchor="w"
        ).grid(row=3, column=0, padx=12, pady=(2, 4), sticky="ew")
        self.multiple_answer_var = ctk.StringVar(value="1번")
        self.multiple_answer_menu = ctk.CTkOptionMenu(
            self.choice_card, variable=self.multiple_answer_var, values=["1번"], height=34
        )
        self.multiple_answer_menu.grid(row=4, column=0, padx=12, pady=(0, 12), sticky="ew")

        # OX
        self.ox_card = self._card(self.answer_area)
        self.ox_card.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(self.ox_card, text="정답", font=(FONT, 10, "bold"), text_color=TEXT).pack(
            anchor="w", padx=12, pady=(12, 5)
        )
        self.ox_answer_var = ctk.StringVar(value="O")
        ctk.CTkSegmentedButton(
            self.ox_card, values=["O", "X"], variable=self.ox_answer_var, height=38
        ).pack(fill="x", padx=12, pady=(0, 12))

        # 주관식
        self.short_card = self._card(self.answer_area)
        self.short_card.grid(row=0, column=0, sticky="ew")
        self.short_card.grid_columnconfigure(0, weight=1)
        self.short_answer_var = ctk.StringVar()
        self.accepted_var = ctk.StringVar()
        self.ignore_space_var = ctk.BooleanVar(value=True)
        self.ignore_punct_var = ctk.BooleanVar(value=True)
        self.ignore_case_var = ctk.BooleanVar(value=True)
        self._easy_entry(self.short_card, 0, "정답", self.short_answer_var, "예: 서울")
        self._easy_entry(
            self.short_card, 2, "이것도 정답으로 인정", self.accepted_var,
            "여러 표현이 있으면 쉼표로 구분 · 예: 서울특별시, Seoul",
        )
        judge = ctk.CTkFrame(self.short_card, fg_color="transparent")
        judge.grid(row=4, column=0, padx=12, pady=(4, 10), sticky="ew")
        ctk.CTkLabel(judge, text="사소한 표기 차이는 정답으로 인정", font=(FONT, 9, "bold"), text_color=MUTED).pack(anchor="w")
        ctk.CTkSwitch(judge, text="띄어쓰기 차이 무시", variable=self.ignore_space_var, font=(FONT, 9)).pack(anchor="w", pady=(5, 0))
        ctk.CTkSwitch(judge, text="문장부호 차이 무시", variable=self.ignore_punct_var, font=(FONT, 9)).pack(anchor="w", pady=(4, 0))
        ctk.CTkSwitch(judge, text="영문 대소문자 차이 무시", variable=self.ignore_case_var, font=(FONT, 9)).pack(anchor="w", pady=(4, 0))

        # 숫자
        self.number_card = self._card(self.answer_area)
        self.number_card.grid(row=0, column=0, sticky="ew")
        self.number_card.grid_columnconfigure(0, weight=1)
        self.number_answer_var = ctk.StringVar()
        self.number_mode_var = ctk.StringVar(value=NUMBER_TO_UI["exact"])
        self.number_tolerance_var = ctk.StringVar(value="0")
        self.closest_count_var = ctk.StringVar(value="3")
        self._easy_entry(self.number_card, 0, "정답 숫자", self.number_answer_var, "예: 2500")
        ctk.CTkLabel(self.number_card, text="채점 방법", font=(FONT, 10, "bold"), text_color=TEXT, anchor="w").grid(
            row=2, column=0, padx=12, pady=(7, 4), sticky="ew"
        )
        ctk.CTkOptionMenu(
            self.number_card,
            variable=self.number_mode_var,
            values=list(NUMBER_TO_UI.values()),
            height=34,
            command=lambda _v: self._update_number_visibility(),
        ).grid(row=3, column=0, padx=12, pady=(0, 6), sticky="ew")
        self.number_exact_frame = ctk.CTkFrame(self.number_card, fg_color="transparent")
        self.number_exact_frame.grid(row=4, column=0, padx=12, pady=(0, 9), sticky="ew")
        self.number_exact_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self.number_exact_frame,
            text="허용 오차 · 0이면 정확히 같은 숫자만 정답",
            font=(FONT, 9), text_color=MUTED, anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkEntry(self.number_exact_frame, textvariable=self.number_tolerance_var, height=32).grid(
            row=1, column=0, pady=(4, 0), sticky="ew"
        )
        self.number_closest_frame = ctk.CTkFrame(self.number_card, fg_color="transparent")
        self.number_closest_frame.grid(row=4, column=0, padx=12, pady=(0, 9), sticky="ew")
        self.number_closest_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self.number_closest_frame, text="가까운 몇 명을 뽑을까요?", font=(FONT, 9), text_color=MUTED, anchor="w"
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkEntry(self.number_closest_frame, textvariable=self.closest_count_var, height=32).grid(
            row=1, column=0, pady=(4, 0), sticky="ew"
        )

        self._section_title(form, 5, "3. 시간과 점수", "기본값 그대로 써도 됩니다.")
        score_card = self._card(form)
        score_card.grid(row=6, column=0, padx=16, pady=(0, 14), sticky="ew")
        score_card.grid_columnconfigure(1, weight=1)
        self.duration_var = ctk.StringVar(value="15")
        self.scoring_var = ctk.StringVar(value=SCORE_TO_UI["all"])
        self.base_points_var = ctk.StringVar(value="100")
        self.first_n_var = ctk.StringVar(value="3")
        self.rank_points_var = ctk.StringVar(value="300, 200, 100")
        self.answer_policy_var = ctk.StringVar(value=POLICY_TO_UI["last"])
        self.auto_time_var = ctk.BooleanVar(value=True)
        self.auto_quota_var = ctk.BooleanVar(value=False)
        self.editor_vars.update(
            {
                "duration": self.duration_var,
                "scoring": self.scoring_var,
                "base_points": self.base_points_var,
                "first_n": self.first_n_var,
                "rank_points": self.rank_points_var,
                "answer_policy": self.answer_policy_var,
                "accepted": self.accepted_var,
            }
        )
        self._score_row(score_card, 0, "답변 시간", self.duration_var, "초")
        ctk.CTkLabel(score_card, text="점수 주는 방법", font=(FONT, 10, "bold"), text_color=TEXT, anchor="w").grid(
            row=1, column=0, padx=12, pady=7, sticky="w"
        )
        ctk.CTkOptionMenu(
            score_card,
            variable=self.scoring_var,
            values=list(SCORE_TO_UI.values()),
            height=34,
            command=lambda _v: self._update_scoring_visibility(),
        ).grid(row=1, column=1, padx=12, pady=6, sticky="ew")
        self._score_row(score_card, 2, "정답 기본 점수", self.base_points_var, "점")
        self.fast_score_frame = ctk.CTkFrame(score_card, fg_color=PANEL_2, corner_radius=10)
        self.fast_score_frame.grid(row=3, column=0, columnspan=2, padx=10, pady=(5, 8), sticky="ew")
        self.fast_score_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            self.fast_score_frame, text="빠른 몇 명까지", font=(FONT, 9, "bold"), text_color=TEXT
        ).grid(row=0, column=0, padx=10, pady=8, sticky="w")
        ctk.CTkEntry(self.fast_score_frame, textvariable=self.first_n_var, width=90, height=30).grid(
            row=0, column=1, padx=10, pady=6, sticky="w"
        )
        ctk.CTkLabel(
            self.fast_score_frame, text="1등부터 줄 점수", font=(FONT, 9, "bold"), text_color=TEXT
        ).grid(row=1, column=0, padx=10, pady=8, sticky="w")
        ctk.CTkEntry(
            self.fast_score_frame, textvariable=self.rank_points_var, height=30,
            placeholder_text="예: 300, 200, 100"
        ).grid(row=1, column=1, padx=10, pady=6, sticky="ew")
        ctk.CTkLabel(
            self.fast_score_frame,
            text="쉼표로 1등, 2등, 3등 순서의 점수를 적습니다.",
            font=(FONT, 8), text_color=MUTED, anchor="w",
        ).grid(row=2, column=0, columnspan=2, padx=10, pady=(0, 8), sticky="ew")
        ctk.CTkLabel(score_card, text="답을 여러 번 보내면", font=(FONT, 10, "bold"), text_color=TEXT, anchor="w").grid(
            row=4, column=0, padx=12, pady=7, sticky="w"
        )
        ctk.CTkOptionMenu(
            score_card, variable=self.answer_policy_var, values=list(POLICY_TO_UI.values()), height=34
        ).grid(row=4, column=1, padx=12, pady=6, sticky="ew")
        switches = ctk.CTkFrame(score_card, fg_color="transparent")
        switches.grid(row=5, column=0, columnspan=2, padx=12, pady=(6, 10), sticky="ew")
        ctk.CTkSwitch(
            switches, text="시간이 끝나면 답변 접수만 자동으로 마감", variable=self.auto_time_var, font=(FONT, 9)
        ).pack(anchor="w", pady=3)
        self.auto_quota_switch = ctk.CTkSwitch(
            switches, text="빠른 인원이 다 차면 답변 접수 자동 마감", variable=self.auto_quota_var, font=(FONT, 9)
        )
        self.auto_quota_switch.pack(anchor="w", pady=3)

        bottom = ctk.CTkFrame(form, fg_color="transparent")
        bottom.grid(row=7, column=0, padx=16, pady=(0, 18), sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)
        self.editor_status = ctk.CTkLabel(
            bottom,
            text="다른 문제로 이동해도 작성 중인 내용은 자동 저장됩니다.",
            font=(FONT, 9), text_color=MUTED, anchor="w",
        )
        self.editor_status.grid(row=0, column=0, columnspan=3, pady=(0, 7), sticky="ew")
        ctk.CTkButton(
            bottom, text="추가 설정", width=96, height=40, corner_radius=10,
            fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT,
            command=self.open_advanced_question_rules,
        ).grid(row=1, column=0, padx=(0, 5), sticky="w")
        ctk.CTkButton(
            bottom, text="저장", width=112, height=40, corner_radius=10,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, font=(FONT, 11, "bold"),
            command=self.save_current_question,
        ).grid(row=1, column=1, padx=5, sticky="e")
        ctk.CTkButton(
            bottom, text="저장하고 다음 문제", width=150, height=40, corner_radius=10,
            fg_color=GOOD, hover_color="#289C69", font=(FONT, 11, "bold"),
            command=self.save_and_next_question,
        ).grid(row=1, column=2, padx=(5, 0), sticky="e")

        self._editor_ready = True
        self._refresh_editor_navigation()
        self._load_editor_question()
        return page

    @staticmethod
    def _card(parent) -> ctk.CTkFrame:
        return ctk.CTkFrame(parent, fg_color=PANEL_2, corner_radius=11, border_width=1, border_color=LINE)

    @staticmethod
    def _section_title(parent, row: int, title: str, desc: str) -> None:
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.grid(row=row, column=0, padx=16, pady=(14 if row else 10, 7), sticky="ew")
        ctk.CTkLabel(box, text=title, font=(FONT, 13, "bold"), text_color=TEXT, anchor="w").pack(fill="x")
        ctk.CTkLabel(box, text=desc, font=(FONT, 9), text_color=MUTED, anchor="w").pack(fill="x", pady=(1, 0))

    @staticmethod
    def _easy_entry(parent, row: int, title: str, var: ctk.StringVar, hint: str) -> None:
        ctk.CTkLabel(parent, text=title, font=(FONT, 10, "bold"), text_color=TEXT, anchor="w").grid(
            row=row, column=0, padx=12, pady=(10 if row == 0 else 5, 3), sticky="ew"
        )
        ctk.CTkEntry(parent, textvariable=var, height=34, placeholder_text=hint).grid(
            row=row + 1, column=0, padx=12, pady=(0, 7), sticky="ew"
        )

    @staticmethod
    def _score_row(parent, row: int, title: str, var: ctk.StringVar, unit: str) -> None:
        ctk.CTkLabel(parent, text=title, font=(FONT, 10, "bold"), text_color=TEXT, anchor="w").grid(
            row=row, column=0, padx=12, pady=7, sticky="w"
        )
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.grid(row=row, column=1, padx=12, pady=5, sticky="ew")
        box.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(box, textvariable=var, height=32).grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(box, text=unit, width=28, font=(FONT, 9), text_color=MUTED).grid(row=0, column=1, padx=(6, 0))

    # ---------- editor navigation / autosave ----------
    def _mark_editor_dirty(self) -> None:
        if not self._editor_loading and hasattr(self, "editor_status"):
            self.editor_status.configure(text="수정 중 · 다른 문제로 이동해도 자동 저장됩니다.", text_color=WARNING)

    def _choices_changed(self, _event=None) -> None:
        self._mark_editor_dirty()
        self._refresh_choice_answer_menu(keep_index=True)

    def _choice_lines(self) -> list[str]:
        if not hasattr(self, "choices_box"):
            return []
        return [x.strip() for x in self.choices_box.get("1.0", "end").splitlines() if x.strip()][:6]

    def _refresh_choice_answer_menu(self, keep_index: bool = True) -> None:
        choices = self._choice_lines()
        old = self._selected_choice_index() if keep_index else 1
        values = [f"{i}번 · {text[:70]}" for i, text in enumerate(choices, start=1)] or ["1번"]
        self.multiple_answer_menu.configure(values=values)
        old = max(1, min(old, len(values)))
        self.multiple_answer_var.set(values[old - 1])

    def _selected_choice_index(self) -> int:
        text = self.multiple_answer_var.get() if hasattr(self, "multiple_answer_var") else "1"
        match = re.match(r"\s*(\d+)", str(text))
        return max(1, safe_int(match.group(1), 1)) if match else 1

    def _editor_type_changed(self, _value=None) -> None:
        self._update_kind_visibility()
        self._mark_editor_dirty()

    def _update_kind_visibility(self) -> None:
        if not hasattr(self, "choice_card"):
            return
        selected = self.kind_var.get()
        cards = {
            "객관식": self.choice_card,
            "OX": self.ox_card,
            "주관식": self.short_card,
            "숫자 맞히기": self.number_card,
        }
        for label, card in cards.items():
            if label == selected:
                card.grid()
            else:
                card.grid_remove()
        self._update_number_visibility()

    def _update_number_visibility(self) -> None:
        if not hasattr(self, "number_exact_frame"):
            return
        closest = self.number_mode_var.get() == NUMBER_TO_UI["closest"]
        if closest:
            self.number_exact_frame.grid_remove()
            self.number_closest_frame.grid()
        else:
            self.number_closest_frame.grid_remove()
            self.number_exact_frame.grid()

    def _update_scoring_visibility(self) -> None:
        if not hasattr(self, "fast_score_frame"):
            return
        fast = self.scoring_var.get() != SCORE_TO_UI["all"]
        if fast:
            self.fast_score_frame.grid()
            self.auto_quota_switch.pack(anchor="w", pady=3)
        else:
            self.fast_score_frame.grid_remove()
            self.auto_quota_switch.pack_forget()

    def _current_editor_index(self) -> int:
        rows = self.quiz_sets.get(self.active_set_name, [])
        if not rows:
            return 0
        return max(0, min(len(rows) - 1, safe_int(self.question_index_var.get(), 1) - 1))

    def _refresh_editor_navigation(self) -> None:
        if not hasattr(self, "question_list"):
            return
        rows = self.quiz_sets.get(self.active_set_name, [])
        if not rows:
            self.quiz_sets[self.active_set_name] = [Question(prompt="")]
            rows = self.quiz_sets[self.active_set_name]
        current = max(0, min(len(rows) - 1, self._current_editor_index()))
        self.question_index_var.set(str(current + 1))
        for child in self.question_list.winfo_children():
            child.destroy()
        self.question_buttons = []
        for idx, q in enumerate(rows):
            prompt = str(q.prompt or "").strip().replace("\n", " ") or "문제 내용을 입력하세요"
            if len(prompt) > 44:
                prompt = prompt[:41] + "..."
            label = f"Q{idx + 1}  ·  {KIND_TO_UI.get(q.kind, '문제')}\n{prompt}"
            selected = idx == current
            btn = ctk.CTkButton(
                self.question_list,
                text=label,
                height=58,
                anchor="w",
                corner_radius=9,
                fg_color=("#DFE7FB", "#1A2743") if selected else "transparent",
                hover_color=PANEL_3,
                text_color=TEXT,
                font=(FONT, 10, "bold" if selected else "normal"),
                command=lambda i=idx: self._select_editor_question(i),
            )
            btn.grid(row=idx, column=0, padx=1, pady=2, sticky="ew")
            self.question_buttons.append(btn)
        self.editor_count_label.configure(text=f"총 {len(rows)}문제 · 현재 Q{current + 1}")

    def _select_editor_question(self, index: int) -> None:
        rows = self.quiz_sets.get(self.active_set_name, [])
        if not rows:
            return
        index = max(0, min(len(rows) - 1, index))
        current = self._current_editor_index()
        if index != current:
            self._save_editor_draft(validate=False, refresh=False)
        self.question_index_var.set(str(index + 1))
        self._refresh_editor_navigation()
        self._load_editor_question()

    def _load_editor_question(self) -> None:
        if not self._editor_ready:
            return
        rows = self.quiz_sets.get(self.active_set_name, [])
        if not rows:
            return
        self._editor_loading = True
        try:
            q = rows[self._current_editor_index()]
            self.kind_var.set(KIND_TO_UI.get(q.kind, "객관식"))
            self.prompt_box.delete("1.0", "end")
            self.prompt_box.insert("1.0", str(q.prompt or ""))
            self.choices_box.delete("1.0", "end")
            self.choices_box.insert("1.0", "\n".join(str(x) for x in q.choices))
            self._refresh_choice_answer_menu(keep_index=False)
            values = self.multiple_answer_menu.cget("values") or ["1번"]
            ai = max(1, min(safe_int(q.answer, 1), len(values)))
            self.multiple_answer_var.set(values[ai - 1])
            self.ox_answer_var.set(str(q.answer or "O").upper() if str(q.answer or "O").upper() in {"O", "X"} else "O")
            self.short_answer_var.set(str(q.answer or ""))
            self.accepted_var.set(", ".join(str(x) for x in q.accepted_answers))
            self.number_answer_var.set(str(q.answer or ""))
            self.number_mode_var.set(NUMBER_TO_UI.get(q.number_mode, NUMBER_TO_UI["exact"]))
            self.number_tolerance_var.set(str(q.number_tolerance))
            self.closest_count_var.set(str(q.closest_count))
            self.duration_var.set(str(q.duration_sec))
            self.scoring_var.set(SCORE_TO_UI.get(q.scoring_mode, SCORE_TO_UI["all"]))
            self.first_n_var.set(str(q.first_n))
            self.base_points_var.set(str(q.base_points))
            self.rank_points_var.set(", ".join(str(x) for x in q.rank_points[:20]))
            self.answer_policy_var.set(POLICY_TO_UI.get(q.answer_policy, POLICY_TO_UI["last"]))
            self.auto_time_var.set(bool(q.auto_close_time))
            self.auto_quota_var.set(bool(q.auto_close_quota))
            self.ignore_space_var.set(bool(q.ignore_space))
            self.ignore_punct_var.set(bool(q.ignore_punct))
            self.ignore_case_var.set(bool(q.ignore_case))
            self._update_kind_visibility()
            self._update_scoring_visibility()
            self._update_number_visibility()
            self.editor_status.configure(
                text="다른 문제로 이동해도 작성 중인 내용은 자동 저장됩니다.", text_color=MUTED
            )
        finally:
            self._editor_loading = False

    def _question_from_editor(self, q: Question) -> Question:
        q.kind = UI_TO_KIND.get(self.kind_var.get(), "multiple")
        q.prompt = self.prompt_box.get("1.0", "end").strip()
        q.choices = self._choice_lines()
        if q.kind == "multiple":
            q.answer = str(self._selected_choice_index())
        elif q.kind == "ox":
            q.answer = self.ox_answer_var.get().strip().upper() or "O"
        elif q.kind == "short":
            q.answer = self.short_answer_var.get().strip()
        else:
            q.answer = self.number_answer_var.get().strip()
        q.accepted_answers = [x.strip() for x in self.accepted_var.get().split(",") if x.strip()][:50]
        q.duration_sec = max(1, min(3600, safe_int(self.duration_var.get(), 15)))
        q.scoring_mode = UI_TO_SCORE.get(self.scoring_var.get(), "all")
        q.first_n = max(1, min(1000, safe_int(self.first_n_var.get(), 3)))
        q.base_points = safe_int(self.base_points_var.get(), 100)
        q.rank_points = [safe_int(x.strip(), 0) for x in self.rank_points_var.get().split(",") if x.strip()][:1000]
        if not q.rank_points:
            q.rank_points = [300, 200, 100]
        q.answer_policy = UI_TO_POLICY.get(self.answer_policy_var.get(), "last")
        q.auto_close_time = bool(self.auto_time_var.get())
        q.auto_close_quota = bool(self.auto_quota_var.get())
        q.ignore_space = bool(self.ignore_space_var.get())
        q.ignore_punct = bool(self.ignore_punct_var.get())
        q.ignore_case = bool(self.ignore_case_var.get())
        q.number_mode = UI_TO_NUMBER.get(self.number_mode_var.get(), "exact")
        q.number_tolerance = max(0.0, safe_float(self.number_tolerance_var.get(), 0.0))
        q.closest_count = max(1, min(1000, safe_int(self.closest_count_var.get(), 3)))
        return q

    @staticmethod
    def _validate_editor_question(q: Question) -> str:
        if not str(q.prompt or "").strip():
            return "문제 내용을 입력해주세요."
        if q.kind == "multiple":
            if len(q.choices) < 2:
                return "객관식은 보기를 2개 이상 입력해주세요."
            answer = safe_int(q.answer, 0)
            if answer < 1 or answer > len(q.choices):
                return "정답 보기를 하나 골라주세요."
        elif q.kind == "ox":
            if str(q.answer).upper() not in {"O", "X"}:
                return "정답을 O 또는 X 중에서 골라주세요."
        elif q.kind == "short":
            if not str(q.answer or "").strip():
                return "주관식 정답을 입력해주세요."
        elif q.kind == "number":
            try:
                float(str(q.answer).strip())
            except Exception:
                return "숫자 맞히기 정답에는 숫자를 입력해주세요."
        if q.scoring_mode in {"first_n", "mixed"} and q.first_n < 1:
            return "빠른 사람 수는 1명 이상이어야 합니다."
        return ""

    def _save_editor_draft(self, *, validate: bool, refresh: bool = True) -> bool:
        if not self._editor_ready or self._editor_loading:
            return True
        rows = self.quiz_sets.get(self.active_set_name, [])
        if not rows:
            return False
        q = self._question_from_editor(rows[self._current_editor_index()])
        if validate:
            error = self._validate_editor_question(q)
            if error:
                if hasattr(self, "editor_status"):
                    self.editor_status.configure(text=error, text_color=DANGER)
                messagebox.showwarning("확인해주세요", error)
                return False
        self._save_quiz_sets()
        # Editing is locked during a live round, so updating the engine here is safe.
        self.engine.set_questions(self.quiz_sets[self.active_set_name])
        if refresh:
            self._refresh_editor_navigation()
        if hasattr(self, "editor_status"):
            self.editor_status.configure(text="저장됨", text_color=GOOD)
        return True

    def save_current_question(self) -> bool:
        return self._save_editor_draft(validate=True, refresh=True)

    def save_and_next_question(self) -> None:
        if not self.save_current_question():
            return
        idx = self._current_editor_index()
        rows = self.quiz_sets[self.active_set_name]
        if idx + 1 < len(rows):
            self._select_editor_question(idx + 1)
        else:
            self.editor_status.configure(text="마지막 문제까지 저장했습니다.", text_color=GOOD)

    def add_question(self) -> None:
        self._save_editor_draft(validate=False, refresh=False)
        rows = self.quiz_sets[self.active_set_name]
        rows.append(Question(prompt=""))
        self._save_quiz_sets()
        self.engine.set_questions(rows)
        self.question_index_var.set(str(len(rows)))
        self._refresh_editor_navigation()
        self._load_editor_question()
        self.after(80, lambda: self.prompt_box.focus_set())

    def duplicate_question(self) -> None:
        self._save_editor_draft(validate=False, refresh=False)
        rows = self.quiz_sets[self.active_set_name]
        idx = self._current_editor_index()
        rows.insert(idx + 1, Question.from_dict(asdict(rows[idx])))
        self._save_quiz_sets()
        self.engine.set_questions(rows)
        self.question_index_var.set(str(idx + 2))
        self._refresh_editor_navigation()
        self._load_editor_question()
        self.editor_status.configure(text="문제를 복제했습니다.", text_color=GOOD)

    def delete_question(self) -> None:
        rows = self.quiz_sets[self.active_set_name]
        if len(rows) <= 1:
            messagebox.showinfo("삭제할 수 없음", "퀴즈에는 최소 1개의 문제가 필요합니다.")
            return
        idx = self._current_editor_index()
        prompt = str(rows[idx].prompt or "문제")[:30]
        if not messagebox.askyesno("문제 삭제", f"Q{idx + 1} · {prompt}\n\n이 문제를 삭제할까요?"):
            return
        rows.pop(idx)
        new_idx = min(idx, len(rows) - 1)
        self.question_index_var.set(str(new_idx + 1))
        self._save_quiz_sets()
        self.engine.set_questions(rows)
        self._refresh_editor_navigation()
        self._load_editor_question()

    def _move_question(self, delta: int) -> None:
        self._save_editor_draft(validate=False, refresh=False)
        rows = self.quiz_sets[self.active_set_name]
        idx = self._current_editor_index()
        target = idx + delta
        if target < 0 or target >= len(rows):
            return
        rows[idx], rows[target] = rows[target], rows[idx]
        self.question_index_var.set(str(target + 1))
        self._save_quiz_sets()
        self.engine.set_questions(rows)
        self._refresh_editor_navigation()
        self._load_editor_question()

    # ---------- quiz/set management ----------
    def _change_active_set(self, name: str) -> None:
        if name == self.active_set_name:
            return
        if self._editor_ready and getattr(self, "_active_page", "") == "문제":
            self._save_editor_draft(validate=False, refresh=False)
        super()._change_active_set(name)

    def new_set(self) -> None:
        dialog = ctk.CTkInputDialog(text="새 퀴즈 이름을 입력해주세요.", title="새 퀴즈")
        name = (dialog.get_input() or "").strip()
        if not name:
            return
        if name in self.quiz_sets:
            messagebox.showinfo("같은 이름이 있음", "이미 같은 이름의 퀴즈가 있습니다.")
            return
        self._save_editor_draft(validate=False, refresh=False)
        self.quiz_sets[name] = [Question(prompt="")]
        self._save_quiz_sets()
        super()._change_active_set(name)

    def open_set_manager(self) -> None:
        self._save_editor_draft(validate=False, refresh=False)
        win = ctk.CTkToplevel(self)
        win.title("퀴즈 관리")
        win.geometry("520x310")
        win.transient(self)
        win.grab_set()
        win.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(win, text="퀴즈 관리", font=(FONT, 20, "bold"), anchor="w").grid(
            row=0, column=0, padx=20, pady=(18, 3), sticky="ew"
        )
        ctk.CTkLabel(
            win, text="현재 퀴즈의 이름을 바꾸거나 필요 없는 퀴즈를 삭제할 수 있습니다.",
            font=(FONT, 9), text_color=MUTED, anchor="w"
        ).grid(row=1, column=0, padx=20, pady=(0, 12), sticky="ew")
        card = ctk.CTkFrame(win, fg_color=PANEL_2, corner_radius=12)
        card.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        name_var = ctk.StringVar(value=self.active_set_name)
        ctk.CTkEntry(card, textvariable=name_var, height=36).grid(row=0, column=0, padx=12, pady=12, sticky="ew")

        def rename() -> None:
            new_name = name_var.get().strip()
            old_name = self.active_set_name
            if not new_name or new_name == old_name:
                return
            if new_name in self.quiz_sets:
                messagebox.showinfo("같은 이름이 있음", "이미 같은 이름의 퀴즈가 있습니다.", parent=win)
                return
            rows = self.quiz_sets.pop(old_name)
            self.quiz_sets[new_name] = rows
            self.active_set_name = new_name
            self.settings["active_set"] = new_name
            self._save_settings()
            self._save_quiz_sets()
            self.engine.set_questions(rows)
            self._sync_set_controls()
            self._refresh_editor_navigation()
            win.destroy()

        def delete() -> None:
            if len(self.quiz_sets) <= 1:
                messagebox.showinfo("삭제할 수 없음", "퀴즈는 최소 하나가 필요합니다.", parent=win)
                return
            if not messagebox.askyesno("퀴즈 삭제", f"'{self.active_set_name}' 퀴즈 전체를 삭제할까요?", parent=win):
                return
            old = self.active_set_name
            self.quiz_sets.pop(old, None)
            self._save_quiz_sets()
            next_name = next(iter(self.quiz_sets))
            self.active_set_name = next_name
            self.settings["active_set"] = next_name
            self._save_settings()
            self.engine.set_questions(self.quiz_sets[next_name])
            self.engine.current_index = 0
            self._sync_set_controls()
            self.question_index_var.set("1")
            self._refresh_editor_navigation()
            self._load_editor_question()
            win.destroy()

        actions = ctk.CTkFrame(win, fg_color="transparent")
        actions.grid(row=3, column=0, padx=20, pady=(10, 18), sticky="ew")
        actions.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(actions, text="이름 변경", height=36, command=rename).grid(row=0, column=0, padx=(0, 5), sticky="ew")
        ctk.CTkButton(
            actions, text="이 퀴즈 삭제", width=110, height=36, fg_color="transparent",
            border_width=1, border_color=LINE, hover_color=PANEL_2, text_color=DANGER, command=delete
        ).grid(row=0, column=1, padx=(5, 0))

    def import_quiz_file(self) -> None:
        path = filedialog.askopenfilename(
            title="퀴즈 파일 불러오기",
            filetypes=[("퀴즈 백업 파일", "*.json"), ("모든 파일", "*.*")],
        )
        if not path:
            return
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            if isinstance(raw, list):
                rows = [Question.from_dict(x) for x in raw if isinstance(x, dict)]
                if not rows:
                    raise ValueError("불러올 문제가 없습니다.")
                self.quiz_sets[self.active_set_name] = rows
            elif isinstance(raw, dict):
                parsed: dict[str, list[Question]] = {}
                for name, items in raw.items():
                    if isinstance(items, list):
                        rows = [Question.from_dict(x) for x in items if isinstance(x, dict)]
                        if rows:
                            parsed[str(name)] = rows
                if not parsed:
                    raise ValueError("불러올 수 있는 퀴즈가 없습니다.")
                self.quiz_sets.update(parsed)
            else:
                raise ValueError("지원하지 않는 퀴즈 파일입니다.")
            self._save_quiz_sets()
            self._sync_set_controls()
            self.engine.set_questions(self.quiz_sets[self.active_set_name])
            self.question_index_var.set("1")
            self._refresh_editor_navigation()
            self._load_editor_question()
            messagebox.showinfo("불러오기 완료", "퀴즈 파일을 불러왔습니다.")
        except Exception as exc:
            messagebox.showerror("불러오기 실패", str(exc))

    def export_quiz_file(self) -> None:
        self._save_editor_draft(validate=False, refresh=False)
        path = filedialog.asksaveasfilename(
            title="퀴즈 백업 저장",
            defaultextension=".json",
            filetypes=[("퀴즈 백업 파일", "*.json")],
            initialfile=f"{self.active_set_name}-백업.json",
        )
        if not path:
            return
        rows = [asdict(q) for q in self.quiz_sets[self.active_set_name]]
        Path(path).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        if hasattr(self, "editor_status"):
            self.editor_status.configure(text="백업 파일을 저장했습니다.", text_color=GOOD)

    # ---------- friendly additional settings ----------
    def open_advanced_question_rules(self) -> None:
        if not self.quiz_sets.get(self.active_set_name):
            return
        self._save_editor_draft(validate=False, refresh=False)
        q = self.quiz_sets[self.active_set_name][self._current_editor_index()]
        win = ctk.CTkToplevel(self)
        win.title("추가 설정")
        win.geometry("650x620")
        win.transient(self)
        win.grab_set()
        win.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(win, text="추가 설정", font=(FONT, 20, "bold"), anchor="w").grid(
            row=0, column=0, columnspan=2, padx=22, pady=(20, 3), sticky="ew"
        )
        ctk.CTkLabel(
            win, text="특수한 퀴즈가 아니라면 기본값 그대로 두셔도 됩니다.",
            font=(FONT, 9), text_color=MUTED, anchor="w"
        ).grid(row=1, column=0, columnspan=2, padx=22, pady=(0, 14), sticky="ew")

        def label(row: int, text: str) -> None:
            ctk.CTkLabel(win, text=text, font=(FONT, 10, "bold"), text_color=TEXT, anchor="w").grid(
                row=row, column=0, padx=(22, 10), pady=8, sticky="w"
            )

        label(2, "이 문제 점수")
        mult = ctk.StringVar(value=str(q.score_multiplier))
        ctk.CTkOptionMenu(win, variable=mult, values=["1.0", "1.5", "2.0", "3.0", "5.0"], height=34).grid(
            row=2, column=1, padx=(0, 22), pady=7, sticky="ew"
        )
        ctk.CTkLabel(
            win, text="1.0은 그대로, 2.0은 두 배 점수입니다.", font=(FONT, 8), text_color=MUTED, anchor="w"
        ).grid(row=3, column=1, padx=(2, 22), pady=(0, 5), sticky="ew")
        label(4, "탈락 방식")
        elim = ctk.StringVar(value=ELIM_TO_UI.get(q.elimination_mode, ELIM_TO_UI["none"]))
        ctk.CTkOptionMenu(win, variable=elim, values=list(ELIM_TO_UI.values()), height=34).grid(
            row=4, column=1, padx=(0, 22), pady=7, sticky="ew"
        )
        allow_elim = ctk.BooleanVar(value=bool(q.allow_eliminated_answers))
        shuffle = ctk.BooleanVar(value=bool(q.shuffle_choices))
        ctk.CTkSwitch(win, text="탈락한 사람도 이후 문제에 답하게 하기", variable=allow_elim, font=(FONT, 9)).grid(
            row=5, column=0, columnspan=2, padx=22, pady=7, sticky="w"
        )
        ctk.CTkSwitch(win, text="객관식 보기 순서를 섞기", variable=shuffle, font=(FONT, 9)).grid(
            row=6, column=0, columnspan=2, padx=22, pady=7, sticky="w"
        )
        label(7, "진행자 메모")
        note = ctk.CTkTextbox(win, height=105, corner_radius=10, fg_color=PANEL_2, border_width=1, border_color=LINE)
        note.grid(row=7, column=1, padx=(0, 22), pady=7, sticky="ew")
        note.insert("1.0", str(q.note or ""))
        ctk.CTkLabel(
            win, text="이 메모는 방송 화면에 나오지 않습니다.", font=(FONT, 8), text_color=MUTED, anchor="w"
        ).grid(row=8, column=1, padx=(2, 22), pady=(0, 8), sticky="ew")

        def save() -> None:
            q.score_multiplier = max(0.0, min(100.0, safe_float(mult.get(), 1.0)))
            q.elimination_mode = UI_TO_ELIM.get(elim.get(), "none")
            q.allow_eliminated_answers = bool(allow_elim.get())
            q.shuffle_choices = bool(shuffle.get())
            q.note = note.get("1.0", "end").strip()[:500]
            self._save_quiz_sets()
            self.engine.set_questions(self.quiz_sets[self.active_set_name])
            if hasattr(self, "editor_status"):
                self.editor_status.configure(text="추가 설정을 저장했습니다.", text_color=GOOD)
            win.destroy()

        ctk.CTkButton(win, text="저장", height=40, command=save).grid(
            row=9, column=0, columnspan=2, padx=22, pady=(12, 20), sticky="ew"
        )

    # ---------- hide technical jargon on the normal broadcast page ----------
    def _render_run_state(self) -> None:
        super()._render_run_state()
        if not hasattr(self, "run_ws_status"):
            return
        d = self.client.diagnostics()
        drops = int(d.get("queueDrops", 0) or 0)
        if self.engine.practice_mode:
            self.run_ws_status.configure(text="● 연습 모드", text_color="#9B7CFF")
            if hasattr(self, "pipeline_label"):
                self.pipeline_label.configure(text="테스트 답변 사용 가능", text_color=MUTED)
        elif d.get("subscribed") and drops == 0:
            self.run_ws_status.configure(text="● 채팅 연결 정상", text_color=GOOD)
            if hasattr(self, "pipeline_label"):
                self.pipeline_label.configure(text="답변 수집 정상", text_color=GOOD)
        elif drops:
            self.run_ws_status.configure(text="● 답변 수집 확인 필요", text_color=DANGER)
            if hasattr(self, "pipeline_label"):
                self.pipeline_label.configure(text=f"누락 가능성 {drops}건", text_color=DANGER)
        elif d.get("threadAlive"):
            self.run_ws_status.configure(text="● 채팅 연결 중", text_color=WARNING)
            if hasattr(self, "pipeline_label"):
                self.pipeline_label.configure(text="잠시 기다려주세요", text_color=MUTED)
        else:
            self.run_ws_status.configure(text="● 채팅 연결 안 됨", text_color=MUTED)
            if hasattr(self, "pipeline_label"):
                self.pipeline_label.configure(text="방송 연결을 확인해주세요", text_color=MUTED)


def _single_instance() -> bool:
    if sys.platform != "win32":
        return True
    try:
        kernel = ctypes.windll.kernel32
        handle = kernel.CreateMutexW(None, False, "SOOPQuizStudio-v0.10-single-instance")
        if not handle:
            return True
        return kernel.GetLastError() != 183
    except Exception:
        return True


def main() -> None:
    if not _single_instance():
        try:
            ctypes.windll.user32.MessageBoxW(
                0, "SOOP Quiz Studio가 이미 실행 중입니다.", "SOOP Quiz Studio", 0x40
            )
        except Exception:
            pass
        return
    QuizAppV10().mainloop()


if __name__ == "__main__":
    main()
