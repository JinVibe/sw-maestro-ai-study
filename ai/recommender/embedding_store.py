from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .catalog import build_lyrics_text
from .models import Song


DEFAULT_EMBEDDING_CACHE_PATH = Path("ai/data/embeddings/lyrics_embeddings.jsonl")
EMBEDDING_SOURCE = "lyrics"


@dataclass(frozen=True)
class CachedEmbedding:
    song_id: str
    model: str
    text_hash: str
    embedding: list[float]
    embedding_source: str = EMBEDDING_SOURCE


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_embedding_cache(path: Path | str) -> dict[str, CachedEmbedding]:
    path = Path(path)
    if not path.exists():
        return {}
    result: dict[str, CachedEmbedding] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        song_id = str(raw.get("songId") or raw.get("song_id"))
        result[song_id] = CachedEmbedding(
            song_id=song_id,
            model=str(raw["model"]),
            text_hash=str(raw["text_hash"]),
            embedding=[float(value) for value in raw["embedding"]],
            embedding_source=str(raw.get("embedding_source") or EMBEDDING_SOURCE),
        )
    return result


def write_embedding_cache(path: Path | str, embeddings: dict[str, CachedEmbedding]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(
            {
                "songId": item.song_id,
                "model": item.model,
                "text_hash": item.text_hash,
                "embedding_source": item.embedding_source,
                "embedding": item.embedding,
            },
            ensure_ascii=False,
        )
        for item in embeddings.values()
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def get_missing_songs(songs: list[Song], cache: dict[str, CachedEmbedding], model: str) -> list[Song]:
    missing: list[Song] = []
    for song in songs:
        cached = cache.get(song.song_id)
        text_hash = hash_text(build_lyrics_text(song))
        if (
            cached is None
            or cached.model != model
            or cached.embedding_source != EMBEDDING_SOURCE
            or cached.text_hash != text_hash
        ):
            missing.append(song)
    return missing
