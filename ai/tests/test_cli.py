from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from ai.recommender import cli
from ai.recommender.embedding_store import CachedEmbedding, write_embedding_cache


class FakeClient:
    def __init__(self, *args, **kwargs) -> None:
        self.calls = 0

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]


class CountingBatchClient:
    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        self.batch_sizes.append(len(texts))
        return [[1.0, 0.0] for _ in texts]


class CliTest(unittest.TestCase):
    def test_recommend_default_embedding_path_is_lyrics_embeddings(self) -> None:
        parser = cli.build_parser()
        args = parser.parse_args(["recommend", "--text", "밤", "--age", "36"])

        self.assertEqual(args.embeddings, "ai/data/embeddings/lyrics_embeddings.jsonl")

    def test_embed_songs_writes_jsonl_cache_with_mock_client(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "songs.jsonl"
            output = Path(tmp) / "embeddings.jsonl"
            catalog.write_text(
                "\n".join(
                    [
                        json.dumps({"songId": "1", "title": "A", "lyrics": "첫 번째 가사"}, ensure_ascii=False),
                        json.dumps({"songId": "2", "title": "B", "lyrics": "두 번째 가사"}, ensure_ascii=False),
                    ]
                ),
                encoding="utf-8",
            )
            with mock.patch("ai.recommender.cli.UpstageEmbeddingClient", FakeClient):
                stdout = StringIO()
                with redirect_stdout(stdout):
                    exit_code = cli.main(["embed-songs", "--input", str(catalog), "--output", str(output)])

            self.assertEqual(exit_code, 0)
            self.assertTrue(output.exists())
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertIn("newly embedded songs: 2", stdout.getvalue())

    def test_embed_songs_skips_rows_without_lyrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "songs.jsonl"
            output = Path(tmp) / "embeddings.jsonl"
            catalog.write_text(
                "\n".join(
                    [
                        json.dumps({"songId": "1", "title": "A", "lyrics": "사랑 노래"}, ensure_ascii=False),
                        json.dumps({"songId": "2", "title": "B", "lyrics": ""}, ensure_ascii=False),
                    ]
                ),
                encoding="utf-8",
            )
            with mock.patch("ai.recommender.cli.UpstageEmbeddingClient", FakeClient):
                stdout = StringIO()
                with redirect_stdout(stdout):
                    exit_code = cli.main(["embed-songs", "--input", str(catalog), "--output", str(output)])

            self.assertEqual(exit_code, 0)
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["songId"], "1")
            self.assertIn("skipped empty lyrics: 1", stdout.getvalue())

    def test_embed_songs_batches_full_catalog_embedding_requests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "songs.jsonl"
            output = Path(tmp) / "embeddings.jsonl"
            catalog.write_text(
                "\n".join(
                    json.dumps({"songId": str(i), "title": f"Song {i}", "lyrics": f"가사 {i}"}, ensure_ascii=False)
                    for i in range(5)
                ),
                encoding="utf-8",
            )
            client = CountingBatchClient()

            stats = cli.embed_songs(catalog, output, client=client, batch_size=2)

            self.assertEqual(client.batch_sizes, [2, 2, 1])
            self.assertEqual(stats["newly embedded songs"], 5)
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 5)

    def test_recommend_outputs_json_with_fake_client(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "songs.jsonl"
            embeddings = Path(tmp) / "embeddings.jsonl"
            rows = [
                {
                    "songId": str(i),
                    "title": f"Song {i}",
                    "releaseDate": "2000.01.01",
                    "genres": ["발라드"],
                    "artists": [{"name": f"Artist {i}"}],
                    "lyrics": f"가사 {i}",
                }
                for i in range(7)
            ]
            catalog.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")
            write_embedding_cache(
                embeddings,
                {
                    str(i): CachedEmbedding(str(i), "model", "hash", [1.0, 0.0], "lyrics")
                    for i in range(7)
                },
            )
            with mock.patch("ai.recommender.cli.UpstageEmbeddingClient", FakeClient):
                stdout = StringIO()
                with redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "recommend",
                            "--catalog",
                            str(catalog),
                            "--embeddings",
                            str(embeddings),
                            "--genres",
                            "발라드",
                            "--artists",
                            "조성모",
                            "--text",
                            "밤",
                            "--age",
                            "36",
                            "--bundle-size",
                            "6",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["next_action"], "collect_feedback")
            self.assertEqual(len(result["songs"]), 6)

    def test_recommend_accepts_strategy_weights_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "songs.jsonl"
            embeddings = Path(tmp) / "embeddings.jsonl"
            rows = [
                {"songId": "old", "title": "Old", "releaseDate": "2000.01.01", "artists": [{"name": "A"}], "lyrics": "old"},
                {"songId": "new", "title": "New", "releaseDate": "2025.01.01", "artists": [{"name": "B"}], "lyrics": "new"},
                {"songId": "mid1", "title": "Mid1", "releaseDate": "2010.01.01", "artists": [{"name": "C"}], "lyrics": "mid"},
                {"songId": "mid2", "title": "Mid2", "releaseDate": "2011.01.01", "artists": [{"name": "D"}], "lyrics": "mid"},
                {"songId": "mid3", "title": "Mid3", "releaseDate": "2012.01.01", "artists": [{"name": "E"}], "lyrics": "mid"},
            ]
            catalog.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")
            write_embedding_cache(
                embeddings,
                {
                    "old": CachedEmbedding("old", "model", "hash", [1.0, 0.0], "lyrics"),
                    "new": CachedEmbedding("new", "model", "hash", [0.0, 1.0], "lyrics"),
                    "mid1": CachedEmbedding("mid1", "model", "hash", [0.2, 0.8], "lyrics"),
                    "mid2": CachedEmbedding("mid2", "model", "hash", [0.2, 0.8], "lyrics"),
                    "mid3": CachedEmbedding("mid3", "model", "hash", [0.2, 0.8], "lyrics"),
                },
            )
            with mock.patch("ai.recommender.cli.UpstageEmbeddingClient", FakeClient):
                stdout = StringIO()
                with redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "recommend",
                            "--catalog",
                            str(catalog),
                            "--embeddings",
                            str(embeddings),
                            "--text",
                            "밤",
                            "--age",
                            "36",
                            "--strategy-weights",
                            '{"w_theme": 0.0, "w_era": 1.0, "w_discovery": 0.0, "w_quality": 0.0}',
                            "--bundle-size",
                            "5",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["songs"][0]["song_id"], "mid3")

    def test_recommend_cli_does_not_accept_preferred_year_center_input(self) -> None:
        parser = cli.build_parser()

        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(
                    [
                        "recommend",
                        "--text",
                        "밤",
                        "--age",
                        "36",
                        "--preferred-year-center",
                        "2008.5",
                    ]
                )


if __name__ == "__main__":
    unittest.main()
