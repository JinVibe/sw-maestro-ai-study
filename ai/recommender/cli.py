from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .catalog import build_lyrics_text, load_songs
from .embedding_store import (
    CachedEmbedding,
    DEFAULT_EMBEDDING_CACHE_PATH,
    get_missing_songs,
    hash_text,
    load_embedding_cache,
    write_embedding_cache,
)
from .engine import RecommendationEngine
from .models import RecommendationRequest
from .upstage_client import PASSAGE_MODEL, UpstageEmbeddingClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI recommendation module CLI")
    subcommands = parser.add_subparsers(dest="command", required=True)

    embed = subcommands.add_parser("embed-songs", help="Build song embedding cache")
    embed.add_argument("--input", required=True)
    embed.add_argument("--output", required=True)
    embed.add_argument("--batch-size", type=int, default=32)

    recommend = subcommands.add_parser("recommend", help="Recommend a song bundle")
    recommend.add_argument("--catalog", default="ai/data/samples/melon_kpop_sample.jsonl")
    recommend.add_argument("--embeddings", default=DEFAULT_EMBEDDING_CACHE_PATH.as_posix())
    recommend.add_argument("--genres", nargs="*", default=[])
    recommend.add_argument("--artists", nargs="*", default=[])
    recommend.add_argument("--text", default="")
    recommend.add_argument("--context-text", default="", help="Optional orchestrator context text for future LLM-based recommendation.")
    recommend.add_argument("--age", type=int, required=True)
    recommend.add_argument("--strategy-weights", default="", help="JSON object with w_theme, w_era, w_discovery, w_quality.")
    recommend.add_argument("--bundle-size", type=int, default=5)
    recommend.add_argument("--exclude-song-ids", nargs="*", default=[])
    recommend.add_argument("--embedding-batch-size", type=int, default=32)
    return parser


def embed_songs(
    input_path: Path,
    output_path: Path,
    client: UpstageEmbeddingClient | None = None,
    batch_size: int = 32,
) -> dict[str, int | str]:
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")
    client = client or UpstageEmbeddingClient()
    songs = load_songs(input_path)
    embeddable_songs = [song for song in songs if build_lyrics_text(song)]
    cache = load_embedding_cache(output_path)
    missing = get_missing_songs(embeddable_songs, cache, PASSAGE_MODEL)
    newly_embedded = 0
    for start in range(0, len(missing), batch_size):
        batch = missing[start : start + batch_size]
        texts = [build_lyrics_text(song) for song in batch]
        vectors = client.embed_passages(texts)
        for song, vector, text in zip(batch, vectors, texts):
            cache[song.song_id] = CachedEmbedding(song.song_id, PASSAGE_MODEL, hash_text(text), vector)
            newly_embedded += 1
        write_embedding_cache(output_path, cache)
    if not missing:
        write_embedding_cache(output_path, cache)
    return {
        "total songs": len(songs),
        "skipped empty lyrics": len(songs) - len(embeddable_songs),
        "cached songs": len(embeddable_songs) - len(missing),
        "newly embedded songs": newly_embedded,
        "output path": str(output_path),
    }


def recommend(args: argparse.Namespace, client: UpstageEmbeddingClient | None = None) -> dict:
    songs = load_songs(args.catalog)
    embeddings = load_embedding_cache(args.embeddings)
    strategy_weights = json.loads(args.strategy_weights) if args.strategy_weights else None
    engine = RecommendationEngine(
        songs,
        embeddings,
        client or UpstageEmbeddingClient(),
        embedding_cache_path=Path(args.embeddings),
        embedding_batch_size=args.embedding_batch_size,
    )
    bundle = engine.recommend(
        RecommendationRequest(
            preferred_genres=args.genres,
            preferred_artists=args.artists,
            age=args.age,
            free_text=args.text,
            context_text=args.context_text,
            exclude_song_ids=args.exclude_song_ids,
            strategy_weights=strategy_weights,
            options={"bundle_size": args.bundle_size},
        )
    )
    return bundle.to_dict()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "embed-songs":
        stats = embed_songs(Path(args.input), Path(args.output), batch_size=args.batch_size)
        for key, value in stats.items():
            print(f"{key}: {value}")
        return 0
    if args.command == "recommend":
        print(json.dumps(recommend(args), ensure_ascii=False, indent=2))
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
