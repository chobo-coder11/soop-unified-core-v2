from __future__ import annotations

import os
import re
import string
import unicodedata
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

APP_NAME = "SOOP Quiz Overlay"
APP_VERSION = "0.3.0"
DEFAULT_PORT = 8765
QUIZ_FILE = "quiz_sets.json"
SETTINGS_FILE = "settings.json"
SESSION_FILE = "session_recovery.json"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def app_data_dir() -> Path:
    base = os.getenv("APPDATA") or os.getenv("LOCALAPPDATA") or str(Path.home())
    p = Path(base) / "SOOPQuizOverlay"
    p.mkdir(parents=True, exist_ok=True)
    return p


def norm_short(text: str, *, ignore_space: bool, ignore_punct: bool, ignore_case: bool) -> str:
    text = unicodedata.normalize("NFKC", text.strip())
    if ignore_case:
        text = text.casefold()
    if ignore_space:
        text = re.sub(r"\s+", "", text)
    if ignore_punct:
        punct = string.punctuation + "·ㆍ…‘’“”「」『』【】（）()[]{}<>"
        table = str.maketrans("", "", punct)
        text = text.translate(table)
    return text


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


@dataclass
class Question:
    kind: str = "multiple"
    prompt: str = ""
    choices: list[str] = field(default_factory=lambda: ["보기 1", "보기 2", "보기 3", "보기 4"])
    answer: str = "1"
    accepted_answers: list[str] = field(default_factory=list)
    duration_sec: int = 15
    scoring_mode: str = "all"
    first_n: int = 3
    base_points: int = 100
    rank_points: list[int] = field(default_factory=lambda: [300, 200, 100])
    answer_policy: str = "last"
    auto_close_time: bool = True
    auto_close_quota: bool = False
    ignore_space: bool = True
    ignore_punct: bool = True
    ignore_case: bool = True
    number_tolerance: float = 0.0

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Question":
        q = cls()
        for k in asdict(q).keys():
            if k in d:
                setattr(q, k, d[k])
        q.duration_sec = max(1, min(3600, safe_int(q.duration_sec, 15)))
        q.first_n = max(1, min(1000, safe_int(q.first_n, 3)))
        q.base_points = safe_int(q.base_points, 100)
        q.number_tolerance = max(0.0, safe_float(q.number_tolerance, 0.0))
        q.choices = [str(x) for x in (q.choices or [])][:6]
        q.accepted_answers = [str(x) for x in (q.accepted_answers or [])][:50]
        q.rank_points = [safe_int(x, 0) for x in (q.rank_points or [])][:1000]
        return q


@dataclass
class Participant:
    user_id: str
    nickname: str
    joined_at: str
    correct_count: int = 0
    score: int = 0
    streak: int = 0
    best_streak: int = 0
    total_correct_elapsed_ms: int = 0
    correct_elapsed_samples: int = 0

    @property
    def display(self) -> str:
        return f"{self.nickname}({self.user_id})"


@dataclass
class AnswerRecord:
    user_id: str
    nickname: str
    raw_answer: str
    normalized_answer: str
    seq: int
    received_at: str
    elapsed_ms: int
    correct: bool
    rank: Optional[int] = None
