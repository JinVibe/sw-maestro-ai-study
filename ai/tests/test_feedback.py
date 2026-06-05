from __future__ import annotations

import unittest

from ai.recommender.feedback import (
    count_unknown_streak,
    next_action_from_feedback,
    process_feedback,
    rating_to_signal,
    update_preferred_year_center,
)
from ai.recommender.models import Feedback, ScoreBreakdown


class FeedbackTest(unittest.TestCase):
    def test_rating_to_signal_maps_one_to_five(self) -> None:
        self.assertEqual([rating_to_signal(i) for i in range(1, 6)], [-1.0, -0.5, 0.0, 0.5, 1.0])

    def test_unknown_three_times_returns_follow_up_question(self) -> None:
        feedbacks = [Feedback(song_id=str(i), reaction="몰라요", rating=3) for i in range(3)]

        self.assertEqual(count_unknown_streak(feedbacks, 0), 3)
        self.assertEqual(next_action_from_feedback(feedbacks, 0), "follow_up_question")

    def test_update_preferred_year_center_uses_agent_numeric_shift(self) -> None:
        self.assertEqual(update_preferred_year_center(2012.5, era_shift=-4), 2008.5)
        self.assertEqual(update_preferred_year_center(2012.5, era_shift=4), 2016.5)
        self.assertEqual(update_preferred_year_center(2012.5, era_shift=0), 2012.5)

    def test_update_preferred_year_center_clamps_to_dataset_range(self) -> None:
        self.assertEqual(update_preferred_year_center(2001, era_shift=-4), 2000)
        self.assertEqual(update_preferred_year_center(2024, era_shift=4), 2025)

    def test_process_feedback_returns_next_recommendation_profile_state(self) -> None:
        feedbacks = [
            Feedback(
                song_id="1",
                reaction="듣고 싶어요",
                rating=5,
                score_breakdown=ScoreBreakdown(
                    theme=0.1,
                    era=0.9,
                    discovery=0.1,
                    quality=0.1,
                    penalties=0.0,
                    final=0.0,
                ),
            )
        ]

        updated = process_feedback(
            feedbacks=feedbacks,
            preferred_year_center=2012.5,
            era_shift=-4,
            previous_unknown_streak=0,
        )

        self.assertEqual(updated.preferred_year_center, 2008.5)
        self.assertEqual(updated.next_action, "recommend_next_bundle")
        self.assertEqual(updated.unknown_streak, 0)
        self.assertFalse(hasattr(updated, "updated_weights"))

    def test_process_feedback_calculates_initial_preferred_year_center_from_age(self) -> None:
        updated = process_feedback(
            feedbacks=[],
            preferred_year_center=None,
            age=36,
            era_shift=-4,
            previous_unknown_streak=0,
        )

        self.assertEqual(updated.preferred_year_center, 2008.5)


if __name__ == "__main__":
    unittest.main()
