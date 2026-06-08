from __future__ import annotations

import unittest

from ai.orchestrator.nodes import build_candidate_pool


class CandidatePoolTest(unittest.TestCase):
    def test_build_candidate_pool_prefers_era_genre_artist_and_text_matches(self) -> None:
        state = {
            "age": 36,
            "preferred_genres": ["발라드"],
            "preferred_artists": ["조성모"],
            "free_text": "밤에 산책할 때 듣고 싶어요",
            "candidate_source": [
                {
                    "song_id": "song-1",
                    "title": "밤의 산책",
                    "artists": ["조성모"],
                    "album": "앨범 1",
                    "release_date": "2008-01-01",
                    "genres": ["발라드"],
                    "like_count": 10,
                    "lyrics": "밤에 산책하며 듣기 좋은 노래",
                },
                {
                    "song_id": "song-2",
                    "title": "댄스 타임",
                    "artists": ["댄스가수"],
                    "album": "앨범 2",
                    "release_date": "2019-01-01",
                    "genres": ["댄스"],
                    "like_count": 200,
                    "lyrics": "신나는 무대",
                },
                {
                    "song_id": "song-3",
                    "title": "비슷한 감성",
                    "artists": ["다른가수"],
                    "album": "앨범 3",
                    "release_date": "2007-01-01",
                    "genres": ["발라드"],
                    "like_count": 20,
                    "lyrics": "밤 산책과 어울리는 감성",
                },
            ],
        }

        result = build_candidate_pool(state)

        self.assertEqual(result["candidate_pool_count"], 3)
        self.assertEqual(result["candidate_pool"][0]["song_id"], "song-1")
        self.assertEqual(result["candidate_pool"][0]["match_signals"]["era"], 1.0)
        self.assertEqual(result["candidate_pool"][0]["match_signals"]["genre"], 1.0)
        self.assertEqual(result["candidate_pool"][0]["match_signals"]["artist"], 1.0)
        self.assertGreater(result["candidate_pool"][0]["priority_score"], result["candidate_pool"][1]["priority_score"])
        self.assertGreater(result["candidate_pool"][1]["priority_score"], result["candidate_pool"][2]["priority_score"])

    def test_build_candidate_pool_excludes_song_ids(self) -> None:
        state = {
            "age": 36,
            "preferred_genres": ["발라드"],
            "preferred_artists": ["조성모"],
            "free_text": "밤에 산책할 때 듣고 싶어요",
            "exclude_song_ids": ["song-1"],
            "candidate_source": [
                {
                    "song_id": "song-1",
                    "title": "밤의 산책",
                    "artists": ["조성모"],
                    "album": "앨범 1",
                    "release_date": "2008-01-01",
                    "genres": ["발라드"],
                    "like_count": 10,
                    "lyrics": "밤에 산책하며 듣기 좋은 노래",
                },
                {
                    "song_id": "song-2",
                    "title": "비슷한 감성",
                    "artists": ["다른가수"],
                    "album": "앨범 3",
                    "release_date": "2007-01-01",
                    "genres": ["발라드"],
                    "like_count": 20,
                    "lyrics": "밤 산책과 어울리는 감성",
                },
            ],
        }

        result = build_candidate_pool(state)

        self.assertEqual([item["song_id"] for item in result["candidate_pool"]], ["song-2"])


if __name__ == "__main__":
    unittest.main()
