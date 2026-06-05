from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ai.recommender.catalog import build_lyrics_text, load_songs
from ai.recommender.embedding_store import (
    CachedEmbedding,
    DEFAULT_EMBEDDING_CACHE_PATH,
    get_missing_songs,
    hash_text,
    load_embedding_cache,
    write_embedding_cache,
)


SAMPLE_PATH = Path(__file__).resolve().parents[1] / "data" / "samples" / "melon_kpop_sample.jsonl"


class EmbeddingStoreTest(unittest.TestCase):
    def test_cache_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cache.jsonl"
            expected = {
                "106212": CachedEmbedding(
                    song_id="106212",
                    model="model",
                    text_hash="hash",
                    embedding=[0.1, 0.2],
                )
            }

            write_embedding_cache(path, expected)
            actual = load_embedding_cache(path)

        self.assertEqual(actual, expected)

    def test_missing_songs_reuses_same_hash_and_model(self) -> None:
        song = load_songs(SAMPLE_PATH)[0]
        model = "solar-embedding-1-large-passage"
        cache = {
            song.song_id: CachedEmbedding(
                song_id=song.song_id,
                model=model,
                text_hash=hash_text(build_lyrics_text(song)),
                embedding=[0.1, 0.2],
                embedding_source="lyrics",
            )
        }

        self.assertEqual(get_missing_songs([song], cache, model), [])

    def test_default_cache_path_is_lyrics_embeddings(self) -> None:
        self.assertEqual(DEFAULT_EMBEDDING_CACHE_PATH.as_posix(), "ai/data/embeddings/lyrics_embeddings.jsonl")

    def test_missing_songs_includes_changed_text_hash(self) -> None:
        song = load_songs(SAMPLE_PATH)[0]
        cache = {
            song.song_id: CachedEmbedding(
                song_id=song.song_id,
                model="solar-embedding-1-large-passage",
                text_hash="old-hash",
                embedding=[0.1, 0.2],
                embedding_source="lyrics",
            )
        }

        missing = get_missing_songs([song], cache, "solar-embedding-1-large-passage")

        self.assertEqual(missing, [song])


if __name__ == "__main__":
    unittest.main()
