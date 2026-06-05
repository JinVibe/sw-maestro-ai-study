from __future__ import annotations

import uuid
from pathlib import Path

from .catalog import build_lyrics_text
from .embedding_store import CachedEmbedding
from .errors import RecommendationInputError
from .models import RecommendationBundle, RecommendationRequest, RecommendedSong, Song
from .embedding_store import EMBEDDING_SOURCE, hash_text, write_embedding_cache
from .era import preferred_year_center_from_age, release_year
from .scoring import calculate_final_score, cosine_similarity
from .upstage_client import PASSAGE_MODEL


class RecommendationEngine:
    def __init__(
        self,
        songs: list[Song],
        embeddings: dict[str, CachedEmbedding],
        embedding_client: object,
        embedding_cache_path: Path | None = None,
        embedding_batch_size: int = 32,
    ) -> None:
        self.songs = songs
        self.embeddings = embeddings
        self.embedding_client = embedding_client
        self.embedding_cache_path = embedding_cache_path
        self.embedding_batch_size = embedding_batch_size

    def recommend(self, request: RecommendationRequest) -> RecommendationBundle:
        query_text = request.free_text.strip()
        if not query_text:
            raise RecommendationInputError("free_text is required for lyrics-based recommendation")
        if request.age is None:
            raise RecommendationInputError("age is required for era-aware recommendation")
        query_embedding = self.embedding_client.embed_query(query_text)
        candidates = self._prefilter_candidates(request)
        self._ensure_candidate_embeddings(candidates)
        candidates = [song for song in candidates if self._has_valid_embedding(song)]
        if len(candidates) < request.options.bundle_size:
            raise RecommendationInputError("not enough embeddable candidate songs for requested bundle_size")
        selected: list[Song] = []
        recommended: list[RecommendedSong] = []
        remaining = candidates
        while remaining and len(recommended) < request.options.bundle_size:
            scored = []
            for song in remaining:
                cached = self.embeddings[song.song_id]
                similarity = cosine_similarity(query_embedding, cached.embedding)
                scored.append(
                    (
                        calculate_final_score(
                            song,
                            request,
                            similarity,
                            selected,
                            request.exclude_song_ids,
                            weights=request.strategy_weights,
                        ),
                        song,
                    )
                )
            scored.sort(key=lambda item: item[0].final, reverse=True)
            breakdown, song = scored[0]
            selected.append(song)
            recommended.append(
                RecommendedSong(
                    song_id=song.song_id,
                    title=song.title,
                    artists=[artist.name for artist in song.artists],
                    album=song.album.name,
                    slot_type=self._slot_type(len(recommended), breakdown),
                    reason=self._reason(query_text, breakdown),
                    score_breakdown=breakdown,
                )
            )
            remaining = [song for song in remaining if song.song_id != selected[-1].song_id]
        return RecommendationBundle(
            bundle_id=f"bundle_{uuid.uuid4().hex[:12]}",
            emotion_title=self._emotion_title(request),
            songs=recommended,
        )

    @staticmethod
    def _slot_type(index: int, breakdown) -> str:
        if index == 0:
            return "anchor"
        if breakdown.discovery >= 0.7:
            return "discovery"
        if breakdown.era >= 0.8:
            return "era_match"
        return "theme_match"

    @staticmethod
    def _reason(query_text: str, breakdown) -> str:
        if breakdown.discovery >= 0.7:
            return f"입력한 '{query_text}'와 가사 분위기가 가까우면서 새롭게 느낄 수 있는 곡입니다."
        if breakdown.era >= 0.8:
            return f"입력한 '{query_text}'와 가사 분위기가 가깝고 선호 시대와도 맞는 곡입니다."
        return f"입력한 '{query_text}'와 가사 분위기가 가까운 곡입니다."

    @staticmethod
    def _emotion_title(request: RecommendationRequest) -> str:
        return f"{request.free_text.strip()}에 어울리는 추천 묶음"

    def _prefilter_candidates(self, request: RecommendationRequest) -> list[Song]:
        base = [song for song in self.songs if song.song_id not in set(request.exclude_song_ids) and build_lyrics_text(song)]
        if len(base) < request.options.bundle_size:
            raise RecommendationInputError("not enough candidate songs after excluding unavailable lyrics")
        target_size = max(request.options.bundle_size * 10, 50)
        preferred = [song for song in base if self._matches_onboarding_preference(song, request)]
        pools = [preferred] if preferred else []
        pools.append(base)
        center = request.preferred_year_center
        if center is None:
            center = preferred_year_center_from_age(request.age)
        for pool in pools:
            if not pool:
                continue
            for window in (8.0, 12.5):
                candidates = [song for song in pool if self._is_in_era_window(song, center, window)]
                if len(candidates) >= target_size:
                    return candidates
                if len(candidates) >= request.options.bundle_size:
                    best_available = candidates
            if len(pool) >= target_size:
                return pool
            if len(pool) >= request.options.bundle_size:
                best_available = pool
        if "best_available" in locals():
            return best_available
        raise RecommendationInputError("not enough candidate songs for requested bundle_size")

    @staticmethod
    def _matches_onboarding_preference(song: Song, request: RecommendationRequest) -> bool:
        preferred_genres = {genre.lower() for genre in request.preferred_genres}
        song_genres = {genre.lower() for genre in song.genres}
        preferred_artists = {artist.lower() for artist in request.preferred_artists}
        song_artists = {artist.name.lower() for artist in song.artists}
        return bool((preferred_genres and preferred_genres & song_genres) or (preferred_artists and preferred_artists & song_artists))

    @staticmethod
    def _is_in_era_window(song: Song, center: float, window: float) -> bool:
        year = release_year(song)
        return year is not None and abs(year - center) <= window

    def _has_valid_embedding(self, song: Song) -> bool:
        text = build_lyrics_text(song)
        cached = self.embeddings.get(song.song_id)
        return bool(
            text
            and cached is not None
            and cached.model == PASSAGE_MODEL
            and cached.embedding_source == EMBEDDING_SOURCE
            and cached.text_hash == hash_text(text)
        )

    def _ensure_candidate_embeddings(self, candidates: list[Song]) -> None:
        missing = [song for song in candidates if not self._has_valid_embedding(song)]
        for start in range(0, len(missing), self.embedding_batch_size):
            batch = missing[start : start + self.embedding_batch_size]
            texts = [build_lyrics_text(song) for song in batch]
            vectors = self.embedding_client.embed_passages(texts)
            for song, text, vector in zip(batch, texts, vectors):
                self.embeddings[song.song_id] = CachedEmbedding(
                    song_id=song.song_id,
                    model=PASSAGE_MODEL,
                    text_hash=hash_text(text),
                    embedding=vector,
                    embedding_source=EMBEDDING_SOURCE,
                )
            if self.embedding_cache_path is not None:
                write_embedding_cache(self.embedding_cache_path, self.embeddings)
