from __future__ import annotations

from .models import Feedback


def count_negative_feedbacks(feedbacks: list[Feedback]) -> int:
    """현재 번들에서 싫어요를 받은 곡의 개수를 셉니다."""

    return sum(1 for feedback in feedbacks if feedback.reaction == "싫어요")
