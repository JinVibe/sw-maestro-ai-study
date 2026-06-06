from __future__ import annotations

from dataclasses import dataclass
from json import loads
from typing import Protocol
from urllib.parse import urlencode
from urllib.request import urlopen

from .models import Song


def normalize_text(value: str) -> str:
    return " ".join(value.casefold().strip().split())


BLOCKED_VARIANT_KEYWORDS = (
    "live",
    "concert",
    "stage",
    "ver.",
    "version",
    "remaster",
    "acoustic",
    "instrumental",
)


@dataclass(frozen=True)
class ItunesTrack:
    track_id: int
    track_name: str
    artist_name: str
    collection_name: str = ""
    preview_url: str = ""
    artwork_url: str = ""
    release_date: str = ""

    @classmethod
    def from_api(cls, payload: dict[str, object]) -> "ItunesTrack":
        return cls(
            track_id=int(payload.get("trackId") or 0),
            track_name=str(payload.get("trackName") or ""),
            artist_name=str(payload.get("artistName") or ""),
            collection_name=str(payload.get("collectionName") or ""),
            preview_url=str(payload.get("previewUrl") or ""),
            artwork_url=str(payload.get("artworkUrl100") or ""),
            release_date=str(payload.get("releaseDate") or ""),
        )


@dataclass(frozen=True)
class VerificationResult:
    track: ItunesTrack
    matched_by: str


class ItunesVerifier(Protocol):
    def verify(self, song: Song) -> VerificationResult | None:
        raise NotImplementedError


class ItunesSearchClient:
    def __init__(
        self,
        country: str = "KR",
        limit: int = 10,
        opener=urlopen,
    ) -> None:
        self.country = country
        self.limit = limit
        self.opener = opener

    def verify(self, song: Song) -> VerificationResult | None:
        for query in self._query_variants(song):
            for track in self.search(query):
                if self._is_verified(song, track):
                    return VerificationResult(track=track, matched_by=query)
        return None

    def search(self, query: str) -> list[ItunesTrack]:
        params = urlencode(
            {
                "term": query,
                "media": "music",
                "entity": "song",
                "country": self.country,
                "limit": str(self.limit),
            }
        )
        with self.opener(f"https://itunes.apple.com/search?{params}") as response:
            payload = loads(response.read().decode("utf-8"))
        return [ItunesTrack.from_api(item) for item in payload.get("results", []) if isinstance(item, dict)]

    def _query_variants(self, song: Song) -> list[str]:
        title = song.title.strip()
        artist = song.artists[0].name.strip() if song.artists else ""
        if artist:
            return [f"{title} {artist}", title]
        return [title]

    def _is_verified(self, song: Song, track: ItunesTrack) -> bool:
        if not track.preview_url:
            return False
        if self._has_blocked_variant(track):
            return False
        song_title = normalize_text(song.title)
        track_title = normalize_text(track.track_name)
        if song_title != track_title and song_title not in track_title and track_title not in song_title:
            return False
        if song.artists:
            candidate_artists = {normalize_text(artist.name) for artist in song.artists if artist.name.strip()}
            if candidate_artists and normalize_text(track.artist_name) not in candidate_artists:
                return False
        return True

    @staticmethod
    def _has_blocked_variant(track: ItunesTrack) -> bool:
        haystack = normalize_text(" ".join([track.track_name, track.collection_name]))
        return any(keyword in haystack for keyword in BLOCKED_VARIANT_KEYWORDS)
