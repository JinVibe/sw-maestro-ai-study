from __future__ import annotations

import unittest

from ai.recommender.feedback import (
    count_negative_feedbacks,
    count_negative_streak,
    count_unknown_streak,
    next_action_from_feedback,
    process_feedback,
    update_preferred_year_center,
)
from ai.recommender.models import Feedback, ScoreBreakdown


class FeedbackTest(unittest.TestCase):
    def test_negative_feedbacks_count_dislikes_in_single_bundle(self) -> None:
        feedbacks = [
            Feedback(song_id="1", reaction="좋아요"),
            Feedback(song_id="2", reaction="싫어요"),
            Feedback(song_id="3", reaction="좋아요"),
            Feedback(song_id="4", reaction="싫어요"),
            Feedback(song_id="5", reaction="싫어요"),
        ]

        self.assertEqual(count_negative_feedbacks(feedbacks), 3)
        self.assertEqual(count_negative_streak(feedbacks), 3)
        self.assertEqual(count_unknown_streak(feedbacks), 3)
        self.assertEqual(next_action_from_feedback(feedbacks), "request_follow_up_text")

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
                reaction="좋아요",
                score_breakdown=ScoreBreakdown(
                    theme=0.1,
                    era=0.9,
                    discovery=0.1,
                    quality=0.1,
                    penalties=0.0,
                    final=0.0,
                ),
            ),
            Feedback(song_id="2", reaction="싫어요"),
            Feedback(song_id="3", reaction="싫어요"),
            Feedback(song_id="4", reaction="좋아요"),
            Feedback(song_id="5", reaction="싫어요"),
        ]

        updated = process_feedback(
            feedbacks=feedbacks,
            preferred_year_center=2012.5,
            era_shift=-4,
        )

        self.assertEqual(updated.preferred_year_center, 2008.5)
        self.assertEqual(updated.next_action, "request_follow_up_text")
        self.assertEqual(updated.negative_count, 3)

    def test_process_feedback_calculates_initial_preferred_year_center_from_age(self) -> None:
        updated = process_feedback(
            feedbacks=[],
            preferred_year_center=None,
            age=36,
            era_shift=-4,
        )

        self.assertEqual(updated.preferred_year_center, 2008.5)
        self.assertEqual(updated.next_action, "recommend_next_bundle")
        self.assertEqual(updated.negative_count, 0)


if __name__ == "__main__":
    unittest.main()
