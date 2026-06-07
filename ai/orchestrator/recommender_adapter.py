from __future__ import annotations

from pathlib import Path
from typing import Any

from ..recommender.catalog import load_songs
from ..recommender.embedding_store import DEFAULT_EMBEDDING_CACHE_PATH, load_embedding_cache
from ..recommender.engine import RecommendationEngine
from ..recommender.errors import MissingEmbeddingCacheError
from ..recommender.models import RecommendationRequest
from ..recommender.upstage_client import UpstageEmbeddingClient


def build_engine(
    catalog_path: str = "ai/data/samples/melon_kpop_sample.jsonl",
    embeddings_path: str = DEFAULT_EMBEDDING_CACHE_PATH,
) -> RecommendationEngine:
    """catalog와 embedding cache를 로드해 RecommendationEngine을 반환한다."""
    songs = load_songs(Path(catalog_path))
    embeddings = load_embedding_cache(Path(embeddings_path))
    if not embeddings:
        raise MissingEmbeddingCacheError(f"임베딩 캐시가 비어 있습니다: {embeddings_path}")
    return RecommendationEngine(
        songs=songs,
        embeddings=embeddings,
        embedding_client=UpstageEmbeddingClient(),
        embedding_cache_path=Path(embeddings_path),
    )


def make_recommender_fn(engine: RecommendationEngine):
    """Orchestrator에 주입할 recommender_fn을 반환한다."""
    def recommender_fn(request: dict[str, Any]) -> dict[str, Any]:
        rec_request = RecommendationRequest(
            user_id=request.get("user_id", ""),
            session_id=request.get("session_id", ""),
            age=request.get("age"),
            preferred_genres=request.get("preferred_genres", []),
            preferred_artists=request.get("preferred_artists", []),
            free_text=request.get("free_text", ""),
            exclude_song_ids=request.get("exclude_song_ids", []),
            strategy_weights=request.get("strategy_weights"),
            options={"bundle_size": 5},
        )
        bundle = engine.recommend(rec_request)
        return bundle.to_dict()

    return recommender_fn
