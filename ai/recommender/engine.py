from __future__ import annotations

import os
import uuid
from pathlib import Path

from .catalog import build_lyrics_text
from .embedding_store import CachedEmbedding
from .errors import RecommendationInputError
from .itunes import ItunesSearchClient, ItunesVerifier, ItunesTrack, VerificationResult
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
        itunes_verifier: ItunesVerifier | None = None,
        embedding_cache_path: Path | None = None,
        embedding_batch_size: int = 32,
    ) -> None:
        self.songs = songs
        self.embeddings = embeddings
        self.embedding_client = embedding_client
        if itunes_verifier is not None:
            self.itunes_verifier = itunes_verifier
        elif os.environ.get("AI_SKIP_ITUNES_VERIFICATION", "").strip().lower() in {"1", "true", "yes"}:
            self.itunes_verifier = _AlwaysVerifiedItunesVerifier()
        else:
            self.itunes_verifier = ItunesSearchClient()
        self.embedding_cache_path = embedding_cache_path
        self.embedding_batch_size = embedding_batch_size

    def recommend(self, request: RecommendationRequest) -> RecommendationBundle:
        query_text = request.free_text.strip()
        if not query_text:
            raise RecommendationInputError("free_text is required for lyrics-based recommendation")
        if request.age is None:
            raise RecommendationInputError("age is required for era-aware recommendation")
        # `context_text`는 앞으로 프롬프트 기반 LLM 경로에서 사용할 예정입니다.
        # 현재 점수 엔진은 동작 안정성을 위해 `free_text`만 사용합니다.
        query_embedding = self.embedding_client.embed_query(query_text)
        candidates = self._prefilter_candidates(request)
        self._ensure_candidate_embeddings(candidates)
        candidates = [song for song in candidates if self._has_valid_embedding(song)]
        if len(candidates) < request.options.bundle_size:
            raise RecommendationInputError("not enough embeddable candidate songs for requested bundle_size")
        selected: list[Song] = []
        selected_identities: set[tuple[str, tuple[str, ...]]] = set()
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
            breakdown = None
            song = None
            verification = None
            rejected_song_ids: set[str] = set()
            for candidate_breakdown, candidate_song in scored:
                candidate_identity = self._song_identity(candidate_song)
                if candidate_identity in selected_identities:
                    continue
                verification = self.itunes_verifier.verify(candidate_song)
                if verification is not None:
                    breakdown = candidate_breakdown
                    song = candidate_song
                    break
                rejected_song_ids.add(candidate_song.song_id)
            if breakdown is None or song is None:
                raise RecommendationInputError("not enough iTunes-verified candidate songs for requested bundle_size")
            track = verification.track if verification is not None else None
            selected.append(song)
            selected_identities.add(self._song_identity(song))
            recommended.append(
                RecommendedSong(
                    song_id=song.song_id,
                    title=song.title,
                    artists=[artist.name for artist in song.artists],
                    album=song.album.name,
                    album_art_url=track.artwork_url if track is not None else "",
                    preview_url=track.preview_url if track is not None else "",
                    slot_type=self._slot_type(len(recommended), breakdown),
                    reason=self._reason(query_text, breakdown),
                    score_breakdown=breakdown,
                )
            )
            remaining = [
                song
                for song in remaining
                if song.song_id != selected[-1].song_id
                and song.song_id not in rejected_song_ids
                and self._song_identity(song) not in selected_identities
            ]
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
        base = self._unique_songs(base)
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

    @classmethod
    def _unique_songs(cls, songs: list[Song]) -> list[Song]:
        unique: list[Song] = []
        seen: set[tuple[str, tuple[str, ...]]] = set()
        for song in songs:
            key = cls._song_identity(song)
            if key in seen:
                continue
            seen.add(key)
            unique.append(song)
        return unique

    @staticmethod
    def _normalize_identity_text(value: str) -> str:
        return " ".join(value.casefold().strip().split())

    @classmethod
    def _song_identity(cls, song: Song) -> tuple[str, tuple[str, ...]]:
        title = cls._normalize_identity_text(song.title)
        artists = tuple(sorted(cls._normalize_identity_text(artist.name) for artist in song.artists if artist.name.strip()))
        return title, artists


class _AlwaysVerifiedItunesVerifier:
    def verify(self, song: Song):
        return VerificationResult(
            track=ItunesTrack(
                track_id=int(song.song_id) if str(song.song_id).isdigit() else 0,
                track_name=song.title,
                artist_name=song.artists[0].name if song.artists else "",
                collection_name=song.album.name,
                preview_url="",
                artwork_url="",
                release_date=song.release_date or "",
            ),
            matched_by="skip",
        )
