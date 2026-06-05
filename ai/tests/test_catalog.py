from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ai.recommender.catalog import build_lyrics_text, load_songs, song_from_raw


SAMPLE_PATH = Path(__file__).resolve().parents[1] / "data" / "samples" / "melon_kpop_sample.jsonl"


class CatalogTest(unittest.TestCase):
    def test_loads_sample_jsonl_as_songs(self) -> None:
        songs = load_songs(SAMPLE_PATH)

        self.assertEqual(len(songs), 100)
        self.assertEqual(songs[0].song_id, "106212")
        self.assertEqual(songs[0].title, "아시나요")
        self.assertEqual(songs[0].artists[0].name, "조성모")
        self.assertEqual(songs[0].genres, ["발라드"])

    def test_song_from_raw_skips_missing_song_id_or_title(self) -> None:
        self.assertIsNone(song_from_raw({"songId": "", "title": "제목"}))
        self.assertIsNone(song_from_raw({"songId": "1", "title": ""}))

    def test_load_songs_keeps_first_duplicate_song_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "songs.jsonl"
            rows = [
                {"songId": "1", "title": "첫 곡"},
                {"songId": "1", "title": "두 번째 곡"},
            ]
            path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")

            songs = load_songs(path)

        self.assertEqual(len(songs), 1)
        self.assertEqual(songs[0].title, "첫 곡")

    def test_build_lyrics_text_uses_only_lyrics(self) -> None:
        song = load_songs(SAMPLE_PATH)[0]
        text = build_lyrics_text(song)

        self.assertTrue(text.startswith("아시나요"))
        self.assertIn("얼마나 사랑했는지", text)
        self.assertNotIn("title:", text)
        self.assertNotIn("artists:", text)
        self.assertNotIn("genres:", text)


if __name__ == "__main__":
    unittest.main()
