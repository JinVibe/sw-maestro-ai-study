from __future__ import annotations

import unittest

from ai.recommender.feedback import rating_to_signal
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

        self.assertEqual(request.options.bundle_size, 6)

    def test_feedback_reaction_is_limited_to_known_values(self) -> None:
        feedback = Feedback(song_id="106212", reaction="듣고 싶어요", rating=5)

        self.assertEqual(feedback.reaction, "듣고 싶어요")
        with self.assertRaises(ValueError):
            Feedback(song_id="106212", reaction="싫어요", rating=3)

    def test_rating_signal_formula(self) -> None:
        self.assertEqual(rating_to_signal(1), -1.0)
        self.assertEqual(rating_to_signal(3), 0.0)
        self.assertEqual(rating_to_signal(5), 1.0)

    def test_recommendation_request_accepts_strategy_weights(self) -> None:
        weights = {"w_theme": 0.0, "w_era": 1.0, "w_discovery": 0.0, "w_quality": 0.0}

        request = RecommendationRequest(free_text="밤", age=36, strategy_weights=weights)

        self.assertEqual(request.strategy_weights, weights)

    def test_updated_profile_includes_preferred_year_center(self) -> None:
        profile = UpdatedProfile(
            preferred_year_center=2008.5,
            unknown_streak=0,
            next_action="recommend_next_bundle",
        )

        self.assertEqual(profile.preferred_year_center, 2008.5)


if __name__ == "__main__":
    unittest.main()
