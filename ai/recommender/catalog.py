from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Album, Artist, Song


def load_songs(path: Path | str) -> list[Song]:
    path = Path(path)
    songs: list[Song] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        song = song_from_raw(json.loads(line))
        if song is None or song.song_id in seen:
            continue
        seen.add(song.song_id)
        songs.append(song)
    return songs


def song_from_raw(raw: dict[str, Any]) -> Song | None:
    song_id = str(raw.get("songId") or raw.get("song_id") or "").strip()
    title = _normalize_catalog_text(raw.get("title"))
    if not song_id or not title:
        return None

    raw_artists = raw.get("artists") or []
    artists = [
        Artist(
            artist_id=str(item.get("artistId") or item.get("artist_id") or ""),
            name=_normalize_catalog_text(item.get("name")),
        )
        for item in raw_artists
        if isinstance(item, dict)
    ]
    raw_album = raw.get("album") or {}
    album = Album(
        album_id=raw_album.get("albumId") or raw_album.get("album_id"),
        name=_normalize_catalog_text(raw_album.get("name")),
    )
    return Song(
        song_id=song_id,
        title=title,
        artists=artists,
        album=album,
        release_date=raw.get("releaseDate") or raw.get("release_date"),
        genres=[_normalize_catalog_text(genre) for genre in raw.get("genres", [])],
        flac=raw.get("flac"),
        like_count=int(raw.get("likeCount") or raw.get("like_count") or 0),
        lyrics=_normalize_catalog_text(raw.get("lyrics")),
        chart_appearances=list(raw.get("chartAppearances") or raw.get("chart_appearances") or []),
        source_urls=dict(raw.get("sourceUrls") or raw.get("source_urls") or {}),
    )


def build_lyrics_text(song: Song) -> str:
    return song.lyrics.strip()


def build_song_text(song: Song) -> str:
    return build_lyrics_text(song)


def _normalize_catalog_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return _repair_utf8_mojibake(text)


def _repair_utf8_mojibake(text: str) -> str:
    if not any(marker in text for marker in ("ì", "ë", "í", "ê", "ð", "ï")):
        return text
    try:
        repaired = text.encode("latin1").decode("utf-8")
    except UnicodeError:
        return text
    return repaired if any("가" <= char <= "힣" for char in repaired) else text
