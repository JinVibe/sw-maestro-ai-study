from __future__ import annotations

import json
import unittest
from pathlib import Path


SAMPLE_PATH = Path(__file__).resolve().parents[1] / "data" / "samples" / "melon_kpop_sample.jsonl"


class SampleDataTest(unittest.TestCase):
    def test_sample_data_has_expected_rows_and_fields(self) -> None:
        rows = [
            json.loads(line)
            for line in SAMPLE_PATH.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]

        self.assertEqual(len(rows), 100)
        self.assertGreaterEqual(
            set(rows[0]),
            {
                "songId",
                "title",
                "artists",
                "album",
                "releaseDate",
                "genres",
                "likeCount",
                "lyrics",
                "chartAppearances",
                "sourceUrls",
            },
        )


if __name__ == "__main__":
    unittest.main()
