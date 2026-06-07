from __future__ import annotations

import unittest

from ai.orchestrator.nodes import build_candidate_pool


class FakePreferenceExpander:
    def __init__(self, expanded_genres: list[str], expanded_artists: list[str]) -> None:
        self.expanded_genres = expanded_genres
        self.expanded_artists = expanded_artists

    def expand_preferences(self, payload: dict[str, object]) -> dict[str, object]:
        preferred_genres = [str(item) for item in payload.get("preferred_genres", [])]  # type: ignore[arg-type]
        preferred_artists = [str(item) for item in payload.get("preferred_artists", [])]  # type: ignore[arg-type]
        return {
            "expanded_preferred_genres": self.expanded_genres or preferred_genres,
            "expanded_preferred_artists": self.expanded_artists or preferred_artists,
            "genre_expansions": {genre: self.expanded_genres or preferred_genres for genre in preferred_genres},
            "artist_expansions": {artist: self.expanded_artists or preferred_artists for artist in preferred_artists},
        }


class PreferenceExpansionNodeTest(unittest.TestCase):
    def test_build_candidate_pool_uses_expanded_genres(self) -> None:
        state = {
            "age": 36,
            "preferred_genres": ["ballad"],
            "candidate_source": [
                {
                    "song_id": "song-a",
                    "title": "Acoustic Song",
                    "artists": ["Artist A"],
                    "album": "Album A",
                    "release_date": "2008-01-01",
                    "genres": ["acoustic"],
                    "like_count": 10,
                    "lyrics": "soft acoustic song",
                },
                {
                    "song_id": "song-b",
                    "title": "Dance Song",
                    "artists": ["Artist B"],
                    "album": "Album B",
                    "release_date": "2008-01-01",
                    "genres": ["dance"],
                    "like_count": 10,
                    "lyrics": "upbeat dance song",
                },
            ],
        }

        result = build_candidate_pool(
            state,
            preference_expander=FakePreferenceExpander(["ballad", "acoustic"], []),
        )

        self.assertEqual(result["expanded_preferred_genres"], ["ballad", "acoustic"])
        self.assertEqual(result["candidate_pool"][0]["song_id"], "song-a")
        self.assertGreater(
            result["candidate_pool"][0]["match_signals"]["genre"],
            result["candidate_pool"][1]["match_signals"]["genre"],
        )

    def test_build_candidate_pool_uses_expanded_artists(self) -> None:
        state = {
            "age": 36,
            "preferred_artists": ["조성모"],
            "candidate_source": [
                {
                    "song_id": "song-a",
                    "title": "Song A",
                    "artists": ["김광석"],
                    "album": "Album A",
                    "release_date": "2008-01-01",
                    "genres": ["ballad"],
                    "like_count": 10,
                    "lyrics": "gentle ballad",
                },
                {
                    "song_id": "song-b",
                    "title": "Song B",
                    "artists": ["Artist B"],
                    "album": "Album B",
                    "release_date": "2008-01-01",
                    "genres": ["dance"],
                    "like_count": 10,
                    "lyrics": "upbeat dance song",
                },
            ],
        }

        result = build_candidate_pool(
            state,
            preference_expander=FakePreferenceExpander([], ["조성모", "김광석"]),
        )

        self.assertEqual(result["expanded_preferred_artists"], ["조성모", "김광석"])
        self.assertEqual(result["candidate_pool"][0]["song_id"], "song-a")
        self.assertGreater(
            result["candidate_pool"][0]["match_signals"]["artist"],
            result["candidate_pool"][1]["match_signals"]["artist"],
        )


if __name__ == "__main__":
    unittest.main()
