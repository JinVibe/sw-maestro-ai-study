from __future__ import annotations

import unittest

from ai.orchestrator.nodes import select_final_5


class FinalSelectionTest(unittest.TestCase):
    def test_select_final_5_deduplicates_and_sets_next_action(self) -> None:
        state = {
            "verified_candidates": [
                {
                    "song_id": "1",
                    "title": "Duplicate",
                    "artists": ["Artist A"],
                    "album": "Album 1",
                    "preview_url": "https://preview.example/1.m4a",
                    "album_art_url": "https://art.example/1.jpg",
                    "selection_reason": "첫 번째 곡",
                },
                {
                    "song_id": "2",
                    "title": "Duplicate",
                    "artists": ["Artist A"],
                    "album": "Album 2",
                    "preview_url": "https://preview.example/2.m4a",
                    "album_art_url": "https://art.example/2.jpg",
                    "selection_reason": "중복 곡",
                },
                {
                    "song_id": "3",
                    "title": "Song 3",
                    "artists": ["Artist B"],
                    "album": "Album 3",
                    "preview_url": "https://preview.example/3.m4a",
                    "album_art_url": "https://art.example/3.jpg",
                },
                {
                    "song_id": "4",
                    "title": "Song 4",
                    "artists": ["Artist C"],
                    "album": "Album 4",
                    "preview_url": "https://preview.example/4.m4a",
                    "album_art_url": "https://art.example/4.jpg",
                },
                {
                    "song_id": "5",
                    "title": "Song 5",
                    "artists": ["Artist D"],
                    "album": "Album 5",
                    "preview_url": "https://preview.example/5.m4a",
                    "album_art_url": "https://art.example/5.jpg",
                },
                {
                    "song_id": "6",
                    "title": "Song 6",
                    "artists": ["Artist E"],
                    "album": "Album 6",
                    "preview_url": "https://preview.example/6.m4a",
                    "album_art_url": "https://art.example/6.jpg",
                },
            ]
        }

        result = select_final_5(state)

        self.assertEqual(result["next_action"], "collect_feedback")
        self.assertEqual(len(result["final_bundle"]), 5)
        self.assertEqual([item["song_id"] for item in result["final_bundle"]], ["1", "3", "4", "5", "6"])
        self.assertEqual(result["final_bundle"][0]["slot_type"], "anchor")
        self.assertEqual(result["final_bundle"][1]["slot_type"], "discovery")


if __name__ == "__main__":
    unittest.main()
