from __future__ import annotations

import unittest

from ai.orchestrator.nodes import verify_with_itunes
from ai.recommender.itunes import ItunesTrack, VerificationResult


class FakeItunesVerifier:
    def __init__(self, verified_song_ids: set[str]) -> None:
        self.verified_song_ids = verified_song_ids

    def verify(self, song):
        if song.song_id not in self.verified_song_ids:
            return None
        return VerificationResult(
            track=ItunesTrack(
                track_id=int(song.song_id),
                track_name=song.title,
                artist_name=song.artists[0].name if song.artists else "",
                collection_name=song.album.name,
                preview_url=f"https://preview.example/{song.song_id}.m4a",
                artwork_url=f"https://art.example/{song.song_id}.jpg",
                release_date=song.release_date or "",
            ),
            matched_by="demo",
        )


class ItunesVerificationNodeTest(unittest.TestCase):
    def test_verify_with_itunes_filters_unverified_candidates(self) -> None:
        state = {
            "selected_candidates": [
                {
                    "song_id": "1",
                    "title": "First",
                    "artists": ["Artist A"],
                    "album": "Album A",
                    "release_date": "2010.01.01",
                    "genres": ["ballad"],
                    "like_count": 10,
                    "lyrics": "lyrics 1",
                },
                {
                    "song_id": "2",
                    "title": "Second",
                    "artists": ["Artist B"],
                    "album": "Album B",
                    "release_date": "2011.01.01",
                    "genres": ["dance"],
                    "like_count": 20,
                    "lyrics": "lyrics 2",
                },
                {
                    "song_id": "3",
                    "title": "Third",
                    "artists": ["Artist C"],
                    "album": "Album C",
                    "release_date": "2012.01.01",
                    "genres": ["indie"],
                    "like_count": 30,
                    "lyrics": "lyrics 3",
                },
            ],
        }

        result = verify_with_itunes(state, verifier=FakeItunesVerifier({"2", "3"}))

        self.assertEqual([item["song_id"] for item in result["verified_candidates"]], ["2", "3"])
        self.assertEqual(result["verified_candidates"][0]["preview_url"], "https://preview.example/2.m4a")
        self.assertEqual(result["verified_candidates"][0]["album_art_url"], "https://art.example/2.jpg")
        self.assertEqual(result["verified_candidates"][0]["itunes_track_id"], 2)
        self.assertEqual(result["verified_candidates"][0]["itunes_matched_by"], "demo")


if __name__ == "__main__":
    unittest.main()
