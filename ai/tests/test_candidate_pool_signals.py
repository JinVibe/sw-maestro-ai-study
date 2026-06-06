from __future__ import annotations

import unittest

from ai.orchestrator.nodes import build_candidate_pool


class CandidatePoolSignalCombinationTest(unittest.TestCase):
    def test_age_only_still_builds_candidate_pool(self) -> None:
        state = {
            "age": 36,
            "candidate_source": [
                {
                    "song_id": "song-a",
                    "title": "Alpha",
                    "artists": ["Artist A"],
                    "album": "Album A",
                    "release_date": "2008-01-01",
                    "genres": ["ballad"],
                    "like_count": 10,
                    "lyrics": "A gentle song from the past",
                },
                {
                    "song_id": "song-b",
                    "title": "Beta",
                    "artists": ["Artist B"],
                    "album": "Album B",
                    "release_date": "2019-01-01",
                    "genres": ["dance"],
                    "like_count": 100,
                    "lyrics": "A modern upbeat song",
                },
            ],
        }

        result = build_candidate_pool(state)

        self.assertEqual(result["candidate_pool_count"], 2)
        self.assertEqual(len(result["candidate_pool"]), 2)
        self.assertIn(result["candidate_pool"][0]["song_id"], {"song-a", "song-b"})

    def test_age_plus_genre_prefers_genre_match(self) -> None:
        state = {
            "age": 36,
            "preferred_genres": ["ballad"],
            "candidate_source": [
                {
                    "song_id": "song-a",
                    "title": "Alpha",
                    "artists": ["Artist A"],
                    "album": "Album A",
                    "release_date": "2008-01-01",
                    "genres": ["ballad"],
                    "like_count": 10,
                    "lyrics": "A gentle song from the past",
                },
                {
                    "song_id": "song-b",
                    "title": "Beta",
                    "artists": ["Artist B"],
                    "album": "Album B",
                    "release_date": "2008-01-01",
                    "genres": ["dance"],
                    "like_count": 100,
                    "lyrics": "A modern upbeat song",
                },
            ],
        }

        result = build_candidate_pool(state)

        self.assertEqual(result["candidate_pool"][0]["song_id"], "song-a")
        self.assertGreater(
            result["candidate_pool"][0]["priority_score"],
            result["candidate_pool"][1]["priority_score"],
        )

    def test_age_plus_artist_plus_text_uses_all_available_signals(self) -> None:
        state = {
            "age": 36,
            "preferred_artists": ["Artist A"],
            "free_text": "night walk",
            "candidate_source": [
                {
                    "song_id": "song-a",
                    "title": "Night Walk",
                    "artists": ["Artist A"],
                    "album": "Album A",
                    "release_date": "2008-01-01",
                    "genres": ["ballad"],
                    "like_count": 10,
                    "lyrics": "night walk gentle mood",
                },
                {
                    "song_id": "song-b",
                    "title": "Another Song",
                    "artists": ["Artist B"],
                    "album": "Album B",
                    "release_date": "2008-01-01",
                    "genres": ["dance"],
                    "like_count": 100,
                    "lyrics": "different mood",
                },
            ],
        }

        result = build_candidate_pool(state)

        self.assertEqual(result["candidate_pool"][0]["song_id"], "song-a")
        self.assertGreater(
            result["candidate_pool"][0]["match_signals"]["artist"],
            result["candidate_pool"][1]["match_signals"]["artist"],
        )
        self.assertGreater(
            result["candidate_pool"][0]["match_signals"]["text"],
            result["candidate_pool"][1]["match_signals"]["text"],
        )


if __name__ == "__main__":
    unittest.main()
