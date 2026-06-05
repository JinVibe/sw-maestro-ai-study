from __future__ import annotations

from .models import Feedback, UpdatedProfile
from .era import DATASET_END_YEAR, DATASET_START_YEAR, preferred_year_center_from_age, shift_preferred_year_center


def rating_to_signal(rating: int) -> float:
    if not 1 <= rating <= 5:
        raise ValueError("rating must be between 1 and 5")
    return (rating - 3) / 2


def count_unknown_streak(feedbacks: list[Feedback], previous_streak: int = 0) -> int:
    streak = previous_streak
    for feedback in feedbacks:
        if feedback.reaction == "몰라요":
            streak += 1
        else:
            streak = 0
    return streak


def next_action_from_feedback(feedbacks: list[Feedback], previous_streak: int = 0) -> str:
    return "follow_up_question" if count_unknown_streak(feedbacks, previous_streak) >= 3 else "recommend_next_bundle"


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
    previous_unknown_streak: int = 0,
    age: int | None = None,
) -> UpdatedProfile:
    if preferred_year_center is None:
        if age is None:
            raise ValueError("age is required when preferred_year_center is not set")
        preferred_year_center = preferred_year_center_from_age(age)
    return UpdatedProfile(
        preferred_year_center=update_preferred_year_center(preferred_year_center, era_shift),
        unknown_streak=count_unknown_streak(feedbacks, previous_unknown_streak),
        next_action=next_action_from_feedback(feedbacks, previous_unknown_streak),
    )
