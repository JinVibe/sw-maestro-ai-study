from __future__ import annotations

import unittest

from ai.recommender.catalog import load_songs
from ai.recommender.models import RecommendationRequest
from ai.recommender.scoring import (
    DEFAULT_WEIGHTS,
    calculate_era_score,
    calculate_final_score,
    calculate_penalties,
    cosine_similarity,
    normalize_strategy_weights,
)
from pathlib import Path


SAMPLE_PATH = Path(__file__).resolve().parents[1] / "data" / "samples" / "melon_kpop_sample.jsonl"


class ScoringTest(unittest.TestCase):
    def test_cosine_similarity_same_vector_is_one(self) -> None:
        self.assertAlmostEqual(cosine_similarity([1, 2, 3], [1, 2, 3]), 1.0)

    def test_excluded_song_gets_strong_penalty(self) -> None:
        song = load_songs(SAMPLE_PATH)[0]

        self.assertGreaterEqual(calculate_penalties(song, [], [song.song_id]), 1.0)

    def test_same_artist_selected_gets_duplicate_penalty(self) -> None:
        songs = load_songs(SAMPLE_PATH)

        self.assertGreater(calculate_penalties(songs[0], [songs[0]], []), 0.0)

    def test_final_score_contains_breakdown(self) -> None:
        song = load_songs(SAMPLE_PATH)[0]
        request = RecommendationRequest(preferred_genres=["발라드"], preferred_artists=["조성모"], age=36)

        breakdown = calculate_final_score(song, request, 0.9, [], [])

        self.assertGreater(breakdown.final, 0.0)
        self.assertGreaterEqual(breakdown.theme, 0.0)
        self.assertGreaterEqual(breakdown.era, 0.0)
        self.assertFalse(hasattr(breakdown, "preference"))

    def test_era_score_uses_preferred_year_center_without_filtering(self) -> None:
        song_2000 = load_songs(SAMPLE_PATH)[0]
        request = RecommendationRequest(age=36, preferred_year_center=2000)

        self.assertGreater(calculate_era_score(song_2000, request), 0.9)
        self.assertIn("w_era", DEFAULT_WEIGHTS)
        self.assertNotIn("w_pref", DEFAULT_WEIGHTS)

    def test_agent_strategy_weights_are_normalized(self) -> None:
        weights = normalize_strategy_weights({"w_theme": 5, "w_era": 2, "w_discovery": 2, "w_quality": 1})

        self.assertAlmostEqual(sum(weights.values()), 1.0)
        self.assertEqual(set(weights), {"w_theme", "w_era", "w_discovery", "w_quality"})

    def test_invalid_agent_strategy_weights_raise_clear_error(self) -> None:
        with self.assertRaises(ValueError):
            normalize_strategy_weights({"w_theme": 1.0, "w_era": 0.0, "w_discovery": 0.0})
        with self.assertRaises(ValueError):
            normalize_strategy_weights({"w_theme": -1.0, "w_era": 1.0, "w_discovery": 0.0, "w_quality": 0.0})
        with self.assertRaises(ValueError):
            normalize_strategy_weights({"w_theme": 0.0, "w_era": 0.0, "w_discovery": 0.0, "w_quality": 0.0})


if __name__ == "__main__":
    unittest.main()
