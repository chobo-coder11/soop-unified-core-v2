from __future__ import annotations

from quiz_engine_v9 import QuizEngineV9


UI_VERSION = "0.10.0"
PRODUCT_NAME = "SOOP Quiz Studio"


class QuizEngineV10(QuizEngineV9):
    """v0.10 keeps v0.9 scoring/transport semantics and improves operator errors."""

    def current_question_error(self) -> str:
        with self.lock:
            q = self.current_question
            if not q:
                return "방송할 문제가 없습니다. '문제 만들기'에서 문제를 하나 추가해주세요."
            if not str(q.prompt or "").strip():
                return "문제 내용이 비어 있습니다. 문제 문장을 입력해주세요."
            if q.kind == "multiple":
                if len(q.choices) < 2:
                    return "객관식은 보기가 최소 2개 필요합니다."
                if any(not str(choice).strip() for choice in q.choices):
                    return "빈 보기가 있습니다. 내용을 입력하거나 빈 줄을 지워주세요."
                try:
                    answer_index = int(str(q.answer).strip())
                except Exception:
                    return "객관식 정답 보기를 다시 선택해주세요."
                if answer_index < 1 or answer_index > len(q.choices):
                    return "객관식 정답 보기를 다시 선택해주세요."
            elif q.kind == "ox":
                if str(q.answer).strip().upper() not in {"O", "X"}:
                    return "OX 정답을 O 또는 X 중에서 골라주세요."
            elif q.kind == "short":
                if not str(q.answer or "").strip():
                    return "주관식 정답을 입력해주세요."
            elif q.kind == "number":
                try:
                    float(str(q.answer).strip())
                except Exception:
                    return "숫자 맞히기 정답에는 숫자만 입력해주세요."
            else:
                return "문제 종류를 다시 선택해주세요."
            if int(q.duration_sec or 0) < 1:
                return "답변 시간은 1초 이상으로 설정해주세요."
            return ""

    def public_state(self):
        state = super().public_state()
        state["app"] = {"name": PRODUCT_NAME, "version": UI_VERSION}
        return state
