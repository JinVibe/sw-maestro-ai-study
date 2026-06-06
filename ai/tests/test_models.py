from __future__ import annotations

import unittest

from ai.recommender.feedback import count_negative_feedbacks
from ai.recommender.models import Feedback, RecommendationRequest, UpdatedProfile


class ModelTest(unittest.TestCase):
    def test_recommendation_request_has_default_bundle_size(self) -> None:
        request = RecommendationRequest(
            user_id="user-1",
            session_id="session-1",
            preferred_genres=["발라드"],
            preferred_artists=["조성모"],
            free_text="밤에 산책할 때 듣고 싶어요",
        )

        self.assertEqual(request.options.bundle_size, 5)

    def test_feedback_reaction_is_limited_to_known_values(self) -> None:
        feedback = Feedback(song_id="106212", reaction="좋아요")

        self.assertEqual(feedback.reaction, "좋아요")
        with self.assertRaises(ValueError):
            Feedback(song_id="106212", reaction="보통")

    def test_negative_feedback_helper_counts_bundle_dislikes(self) -> None:
        feedbacks = [
            Feedback(song_id="1", reaction="좋아요"),
            Feedback(song_id="2", reaction="싫어요"),
            Feedback(song_id="3", reaction="싫어요"),
            Feedback(song_id="4", reaction="좋아요"),
            Feedback(song_id="5", reaction="싫어요"),
        ]

        self.assertEqual(count_negative_feedbacks(feedbacks), 3)

    def test_recommendation_request_accepts_context_text(self) -> None:
        request = RecommendationRequest(
            free_text="공부할 때",
            age=36,
            context_text="최근에 발라드 선호, 싫어요 3곡 발생",
        )

        self.assertEqual(request.context_text, "최근에 발라드 선호, 싫어요 3곡 발생")

    def test_updated_profile_includes_negative_count(self) -> None:
        profile = UpdatedProfile(
            preferred_year_center=2008.5,
            negative_count=3,
            next_action="request_follow_up_text",
        )

        self.assertEqual(profile.preferred_year_center, 2008.5)
        self.assertEqual(profile.negative_count, 3)
        self.assertEqual(profile.next_action, "request_follow_up_text")


if __name__ == "__main__":
    unittest.main()
