from __future__ import annotations

from .era import DATASET_END_YEAR, DATASET_START_YEAR, preferred_year_center_from_age, shift_preferred_year_center
from .models import Feedback, UpdatedProfile


def count_negative_feedbacks(feedbacks: list[Feedback]) -> int:
    """현재 번들 안의 싫어요 개수를 순서와 관계없이 셉니다."""

    return sum(1 for feedback in feedbacks if feedback.reaction == "싫어요")


def next_action_from_feedback(feedbacks: list[Feedback]) -> str:
    return "request_follow_up_text" if count_negative_feedbacks(feedbacks) >= 3 else "recommend_next_bundle"


def update_preferred_year_center(
    preferred_year_center: float,
    era_shift: float = 0.0,
    dataset_start_year: int = DATASET_START_YEAR,
    dataset_end_year: int = DATASET_END_YEAR,
) -> float:
    return shift_preferred_year_center(
        preferred_year_center,
        era_shift,
        dataset_start_year=dataset_start_year,
        dataset_end_year=dataset_end_year,
    )


def process_feedback(
    feedbacks: list[Feedback],
    preferred_year_center: float | None,
    era_shift: float = 0.0,
    age: int | None = None,
) -> UpdatedProfile:
    if preferred_year_center is None:
        if age is None:
            raise ValueError("age is required when preferred_year_center is not set")
        preferred_year_center = preferred_year_center_from_age(age)
    return UpdatedProfile(
        preferred_year_center=update_preferred_year_center(preferred_year_center, era_shift),
        negative_count=count_negative_feedbacks(feedbacks),
        next_action=next_action_from_feedback(feedbacks),
    )


# 이전 호출자와 테스트를 위한 호환 별칭입니다.
count_negative_streak = count_negative_feedbacks
count_unknown_streak = count_negative_feedbacks
