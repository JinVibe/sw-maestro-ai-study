from __future__ import annotations

import json
from io import BytesIO
from unittest import TestCase

from ai.recommender.itunes import ItunesSearchClient
from ai.recommender.models import Album, Artist, Song


class ItunesFilteringTests(TestCase):
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
