from __future__ import annotations

import json
from io import BytesIO
from unittest import TestCase

from ai.recommender.engine import RecommendationEngine
from ai.recommender.embedding_store import CachedEmbedding
from ai.recommender.itunes import ItunesSearchClient, ItunesTrack, VerificationResult
from ai.recommender.models import Album, Artist, RecommendationRequest, Song


class FakeEmbeddingClient:
    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class FakeItunesVerifier:
    def __init__(self, verified: set[str]) -> None:
        self.verified = verified

    def verify(self, song: Song):
        if song.song_id not in self.verified:
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


class ItunesFilteringTests(TestCase):
    def test_engine_skips_unverified_candidates_before_selecting_bundle(self) -> None:
        songs = [
            Song(song_id="1", title="Top", artists=[Artist(name="A")], album=Album(name="Album"), release_date="2012.01.01", lyrics="lyrics 1"),
            Song(song_id="2", title="Second", artists=[Artist(name="B")], album=Album(name="Album"), release_date="2012.01.01", lyrics="lyrics 2"),
            Song(song_id="3", title="Third", artists=[Artist(name="C")], album=Album(name="Album"), release_date="2012.01.01", lyrics="lyrics 3"),
            Song(song_id="4", title="Fourth", artists=[Artist(name="D")], album=Album(name="Album"), release_date="2012.01.01", lyrics="lyrics 4"),
            Song(song_id="5", title="Fifth", artists=[Artist(name="E")], album=Album(name="Album"), release_date="2012.01.01", lyrics="lyrics 5"),
            Song(song_id="6", title="Sixth", artists=[Artist(name="F")], album=Album(name="Album"), release_date="2012.01.01", lyrics="lyrics 6"),
        ]
        embeddings = {
            song.song_id: CachedEmbedding(song.song_id, "model", "hash", [1.0 - index * 0.1, index * 0.1], "lyrics")
            for index, song in enumerate(songs)
        }
        engine = RecommendationEngine(songs, embeddings, FakeEmbeddingClient(), itunes_verifier=FakeItunesVerifier({"2", "3", "4", "5", "6"}))

        bundle = engine.recommend(RecommendationRequest(free_text="밤에 듣고 싶어요", age=36, options={"bundle_size": 5}))

        self.assertEqual([song.song_id for song in bundle.songs], ["2", "3", "4", "5", "6"])

    def test_itunes_search_client_requires_preview_and_matching_track(self) -> None:
        payload = {
            "resultCount": 2,
            "results": [
                {
                    "trackId": 11,
                    "trackName": "Same Title",
                    "artistName": "Same Artist",
                    "collectionName": "Album",
                    "previewUrl": "https://example.com/preview.m4a",
                    "artworkUrl100": "https://example.com/art.jpg",
                    "releaseDate": "2020-01-01T00:00:00Z",
                },
                {
                    "trackId": 12,
                    "trackName": "Same Title",
                    "artistName": "Same Artist",
                    "collectionName": "Album",
                    "previewUrl": "",
                    "artworkUrl100": "https://example.com/art.jpg",
                    "releaseDate": "2020-01-01T00:00:00Z",
                },
            ],
        }

        def opener(url: str):
            class _Response:
                def __enter__(self):
                    return BytesIO(json.dumps(payload).encode("utf-8"))

                def __exit__(self, exc_type, exc, tb):
                    return False

            return _Response()

        client = ItunesSearchClient(opener=opener)
        song = Song(
            song_id="99",
            title="Same Title",
            artists=[Artist(name="Same Artist")],
            album=Album(name="Album"),
            release_date="2020.01.01",
            lyrics="lyrics",
        )

        result = client.verify(song)
        self.assertIsNotNone(result)
        self.assertEqual(result.track.preview_url, "https://example.com/preview.m4a")

    def test_itunes_search_client_skips_live_or_alternate_versions(self) -> None:
        payload = {
            "resultCount": 2,
            "results": [
                {
                    "trackId": 21,
                    "trackName": "Same Title (Live)",
                    "artistName": "Same Artist",
                    "collectionName": "Live Concert 2020",
                    "previewUrl": "https://example.com/live-preview.m4a",
                    "artworkUrl100": "https://example.com/live.jpg",
                    "releaseDate": "2020-01-01T00:00:00Z",
                },
                {
                    "trackId": 22,
                    "trackName": "Same Title",
                    "artistName": "Same Artist",
                    "collectionName": "Studio Album",
                    "previewUrl": "https://example.com/studio-preview.m4a",
                    "artworkUrl100": "https://example.com/studio.jpg",
                    "releaseDate": "2020-01-01T00:00:00Z",
                },
            ],
        }

        def opener(url: str):
            class _Response:
                def __enter__(self):
                    return BytesIO(json.dumps(payload).encode("utf-8"))

                def __exit__(self, exc_type, exc, tb):
                    return False

            return _Response()

        client = ItunesSearchClient(opener=opener)
        song = Song(
            song_id="100",
            title="Same Title",
            artists=[Artist(name="Same Artist")],
            album=Album(name="Studio Album"),
            release_date="2020.01.01",
            lyrics="lyrics",
        )

        result = client.verify(song)
        self.assertIsNotNone(result)
        self.assertEqual(result.track.track_id, 22)
