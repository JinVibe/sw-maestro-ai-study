from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from ai.recommender.catalog import load_songs
from ai.recommender.embedding_store import CachedEmbedding, load_embedding_cache
from ai.recommender.engine import RecommendationEngine
from ai.recommender.errors import RecommendationInputError
from ai.recommender.models import Album, Artist, RecommendationRequest, Song


SAMPLE_PATH = Path(__file__).resolve().parents[1] / "data" / "samples" / "melon_kpop_sample.jsonl"


class FakeEmbeddingClient:
    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class EngineTest(unittest.TestCase):
    def test_recommend_returns_bundle_with_score_breakdown(self) -> None:
        songs = load_songs(SAMPLE_PATH)[:8]
        embeddings = {
            song.song_id: CachedEmbedding(
                song_id=song.song_id,
                model="model",
                text_hash="hash",
                embedding=[1.0 - index * 0.01, index * 0.01],
                embedding_source="lyrics",
            )
            for index, song in enumerate(songs)
        }
        engine = RecommendationEngine(songs, embeddings, FakeEmbeddingClient())

        bundle = engine.recommend(
            RecommendationRequest(
                    preferred_genres=["발라드"],
                    preferred_artists=["조성모"],
                    free_text="밤에 산책할 때 듣고 싶어요",
                    age=36,
                    mood_keywords=["이 값은 query embedding에 들어가면 안 됨"],
                )
            )

        self.assertEqual(len(bundle.songs), 5)
        self.assertEqual(bundle.next_action, "collect_feedback")
        self.assertEqual(len({song.song_id for song in bundle.songs}), 5)
        self.assertIsNotNone(bundle.songs[0].score_breakdown)

    def test_recommend_accepts_bundle_size_between_five_and_seven(self) -> None:
        songs = load_songs(SAMPLE_PATH)[:10]
        embeddings = {
            song.song_id: CachedEmbedding(song.song_id, "model", "hash", [1.0, 0.0], "lyrics")
            for song in songs
        }
        engine = RecommendationEngine(songs, embeddings, FakeEmbeddingClient())

        for size in [5, 6, 7]:
            bundle = engine.recommend(RecommendationRequest(free_text="밤", age=36, options={"bundle_size": size}))
            self.assertEqual(len(bundle.songs), size)

    def test_recommend_requires_free_text_without_fallback(self) -> None:
        songs = load_songs(SAMPLE_PATH)[:5]
        embeddings = {
            song.song_id: CachedEmbedding(song.song_id, "model", "hash", [1.0, 0.0], "lyrics")
            for song in songs
        }
        engine = RecommendationEngine(songs, embeddings, FakeEmbeddingClient())

        with self.assertRaises(RecommendationInputError):
            engine.recommend(RecommendationRequest(preferred_genres=["발라드"]))

    def test_recommend_requires_age(self) -> None:
        songs = load_songs(SAMPLE_PATH)[:5]
        embeddings = {
            song.song_id: CachedEmbedding(song.song_id, "model", "hash", [1.0, 0.0], "lyrics")
            for song in songs
        }
        engine = RecommendationEngine(songs, embeddings, FakeEmbeddingClient())

        with self.assertRaises(RecommendationInputError):
            engine.recommend(RecommendationRequest(free_text="밤"))

    def test_recommend_does_not_hard_filter_by_age_era(self) -> None:
        songs = load_songs(SAMPLE_PATH)[:8]
        embeddings = {
            song.song_id: CachedEmbedding(song.song_id, "model", "hash", [1.0, 0.0], "lyrics")
            for song in songs
        }
        engine = RecommendationEngine(songs, embeddings, FakeEmbeddingClient())

        bundle = engine.recommend(RecommendationRequest(free_text="밤", age=26, options={"bundle_size": 6}))

        self.assertEqual(len(bundle.songs), 6)

    def test_query_embedding_uses_only_free_text(self) -> None:
        class CapturingClient:
            text = ""

            def embed_query(self, text: str) -> list[float]:
                self.text = text
                return [1.0, 0.0]

            def embed_passages(self, texts: list[str]) -> list[list[float]]:
                return [[1.0, 0.0] for _ in texts]

        songs = load_songs(SAMPLE_PATH)[:5]
        embeddings = {
            song.song_id: CachedEmbedding(song.song_id, "model", "hash", [1.0, 0.0], "lyrics")
            for song in songs
        }
        client = CapturingClient()
        engine = RecommendationEngine(songs, embeddings, client)

        engine.recommend(
            RecommendationRequest(
                free_text="밤 산책",
                age=36,
                mood_keywords=["차분함"],
                preferred_genres=["발라드"],
                preferred_artists=["조성모"],
                options={"bundle_size": 5},
            )
        )

        self.assertEqual(client.text, "밤 산책")

    def test_recommend_uses_request_strategy_weights(self) -> None:
        songs = [
            Song(song_id="old", title="Old", artists=[Artist(name="A")], album=Album(name="Album"), release_date="2000.01.01", lyrics="old"),
            Song(song_id="new", title="New", artists=[Artist(name="B")], album=Album(name="Album"), release_date="2025.01.01", lyrics="new"),
            Song(song_id="mid1", title="Mid1", artists=[Artist(name="C")], album=Album(name="Album"), release_date="2010.01.01", lyrics="mid"),
            Song(song_id="mid2", title="Mid2", artists=[Artist(name="D")], album=Album(name="Album"), release_date="2011.01.01", lyrics="mid"),
            Song(song_id="mid3", title="Mid3", artists=[Artist(name="E")], album=Album(name="Album"), release_date="2012.01.01", lyrics="mid"),
        ]
        embeddings = {
            "old": CachedEmbedding("old", "model", "hash", [1.0, 0.0], "lyrics"),
            "new": CachedEmbedding("new", "model", "hash", [0.0, 1.0], "lyrics"),
            "mid1": CachedEmbedding("mid1", "model", "hash", [0.2, 0.8], "lyrics"),
            "mid2": CachedEmbedding("mid2", "model", "hash", [0.2, 0.8], "lyrics"),
            "mid3": CachedEmbedding("mid3", "model", "hash", [0.2, 0.8], "lyrics"),
        }
        engine = RecommendationEngine(songs, embeddings, FakeEmbeddingClient())

        bundle = engine.recommend(
            RecommendationRequest(
                free_text="밤",
                age=36,
                preferred_year_center=2025,
                strategy_weights={"w_theme": 0.0, "w_era": 1.0, "w_discovery": 0.0, "w_quality": 0.0},
                options={"bundle_size": 5},
            )
        )

        self.assertEqual(bundle.songs[0].song_id, "new")

    def test_onboarding_prefilter_prioritizes_matching_genre_or_artist_before_scoring(self) -> None:
        songs = [
            Song(song_id="ballad-old", title="Ballad Old", artists=[Artist(name="A")], album=Album(name="Album"), release_date="2012.01.01", genres=["발라드"], lyrics="lyrics"),
            Song(song_id="dance-old", title="Dance Old", artists=[Artist(name="B")], album=Album(name="Album"), release_date="2012.01.01", genres=["댄스"], lyrics="lyrics"),
            Song(song_id="artist-old", title="Artist Old", artists=[Artist(name="조성모")], album=Album(name="Album"), release_date="2012.01.01", genres=["댄스"], lyrics="lyrics"),
            Song(song_id="dance-new-1", title="Dance New 1", artists=[Artist(name="C")], album=Album(name="Album"), release_date="2025.01.01", genres=["댄스"], lyrics="lyrics"),
            Song(song_id="dance-new-2", title="Dance New 2", artists=[Artist(name="D")], album=Album(name="Album"), release_date="2025.01.01", genres=["댄스"], lyrics="lyrics"),
        ]
        embeddings = {
            song.song_id: CachedEmbedding(song.song_id, "model", "hash", [1.0, 0.0], "lyrics")
            for song in songs
        }
        engine = RecommendationEngine(songs, embeddings, FakeEmbeddingClient())

        bundle = engine.recommend(
            RecommendationRequest(
                free_text="밤",
                age=36,
                preferred_genres=["발라드"],
                preferred_artists=["조성모"],
                preferred_year_center=2012,
                options={"bundle_size": 5},
            )
        )

        self.assertIn(bundle.songs[0].song_id, {"ballad-old", "artist-old"})

    def test_missing_candidate_embeddings_are_generated_and_persisted(self) -> None:
        class CapturingClient(FakeEmbeddingClient):
            def __init__(self) -> None:
                self.passage_texts: list[str] = []

            def embed_passages(self, texts: list[str]) -> list[list[float]]:
                self.passage_texts.extend(texts)
                return [[1.0, 0.0] for _ in texts]

        songs = [
            Song(song_id="cached", title="Cached", artists=[Artist(name="A")], album=Album(name="Album"), release_date="2012.01.01", genres=["발라드"], lyrics="cached lyrics"),
            Song(song_id="missing", title="Missing", artists=[Artist(name="B")], album=Album(name="Album"), release_date="2012.01.01", genres=["발라드"], lyrics="missing lyrics"),
            Song(song_id="empty", title="Empty", artists=[Artist(name="C")], album=Album(name="Album"), release_date="2012.01.01", genres=["발라드"], lyrics=""),
            Song(song_id="other1", title="Other1", artists=[Artist(name="D")], album=Album(name="Album"), release_date="2012.01.01", genres=["발라드"], lyrics="other lyrics 1"),
            Song(song_id="other2", title="Other2", artists=[Artist(name="E")], album=Album(name="Album"), release_date="2012.01.01", genres=["발라드"], lyrics="other lyrics 2"),
            Song(song_id="other3", title="Other3", artists=[Artist(name="F")], album=Album(name="Album"), release_date="2012.01.01", genres=["발라드"], lyrics="other lyrics 3"),
        ]
        embeddings = {"cached": CachedEmbedding("cached", "solar-embedding-1-large-passage", "wrong-hash", [1.0, 0.0], "lyrics")}

        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "lyrics_embeddings.jsonl"
            client = CapturingClient()
            engine = RecommendationEngine(songs, embeddings, client, embedding_cache_path=cache_path, embedding_batch_size=2)

            bundle = engine.recommend(RecommendationRequest(free_text="밤", age=36, preferred_genres=["발라드"], preferred_year_center=2012, options={"bundle_size": 5}))

            persisted = load_embedding_cache(cache_path)

        self.assertEqual(len(bundle.songs), 5)
        self.assertIn("missing lyrics", client.passage_texts)
        self.assertNotIn("", client.passage_texts)
        self.assertIn("missing", persisted)
        self.assertNotIn("empty", persisted)


if __name__ == "__main__":
    unittest.main()
