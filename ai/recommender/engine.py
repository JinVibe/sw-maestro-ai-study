from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Any, Callable, TypedDict

if TYPE_CHECKING:
    from ..orchestrator.state import RecommendationSessionState
from .catalog import load_songs
from .era import preferred_year_center_from_age, release_year
from .feedback import count_negative_feedbacks
from .itunes import ItunesSearchClient
from .models import Album, Artist, Feedback, Song
from .preference_expansion import (
    PreferenceExpansionOutput,
    normalize_expanded_preferences,
)
from .upstage_client import UpstageCandidateSelectorClient, UpstagePreferenceExpanderClient


CANDIDATE_POOL_SIZE = 50
FINAL_BUNDLE_SIZE = 5


class CandidateRecord(TypedDict, total=False):
    song_id: str
    title: str
    artists: list[str]
    album: str
    release_date: str | None
    release_year: int | None
    genres: list[str]
    like_count: int
    lyrics: str
    chart_appearances: list[dict[str, Any]]
    source_urls: dict[str, str]
    preview_url: str
    album_art_url: str
    itunes_track_id: int
    itunes_matched_by: str
    priority_score: float
    score_breakdown: dict[str, float]
    match_signals: dict[str, float]
    selection_reason: str
    selection_order: int


CandidateSelector = Callable[
    [Any, list[CandidateRecord], int],
    list[CandidateRecord],
]


GENRE_ALIAS_GROUPS: dict[str, set[str]] = {
    "발라드": {"발라드", "ballad"},
    "댄스": {"댄스", "dance"},
    "인디": {"인디", "indie"},
    "록": {"록", "rock", "rock music"},
    "r&b": {"r&b", "rnb", "r and b", "알앤비"},
    "힙합": {"힙합", "hiphop", "hip-hop", "rap", "랩"},
    "포크": {"포크", "folk"},
    "어쿠스틱": {"어쿠스틱", "acoustic"},
    "포크록": {"포크록", "folk rock"},
}

GENRE_ALIAS_LOOKUP: dict[str, str] = {
    alias: canonical
    for canonical, aliases in GENRE_ALIAS_GROUPS.items()
    for alias in aliases
}


def build_candidate_pool(
    state: RecommendationSessionState,
    preference_expander: UpstagePreferenceExpanderClient | None = None,
) -> dict[str, Any]:
    source_items = _load_candidate_source_items(state)
    if not source_items:
        raise ValueError("candidate source가 비어 있어 후보 풀을 만들 수 없습니다.")

    exclude_song_ids = {
        song_id.strip()
        for song_id in state.get("exclude_song_ids", [])
        if song_id.strip()
    }
    target_year = _target_year_from_state(state)
    preferred_genres = list(state.get("preferred_genres", []) or [])
    preferred_artists = list(state.get("preferred_artists", []) or [])
    free_text = state.get("free_text", "")
    context = state.get("context", {})

    expanded_preferences = _expand_preferences(
        state,
        preference_expander=preference_expander,
        preferred_genres=preferred_genres,
        preferred_artists=preferred_artists,
    )
    preferred_genres = expanded_preferences["expanded_preferred_genres"] or preferred_genres
    preferred_artists = expanded_preferences["expanded_preferred_artists"] or preferred_artists

    candidate_pool: list[CandidateRecord] = []
    for item in source_items:
        candidate = _candidate_record_from_item(item)
        if candidate is None:
            continue
        song_id = candidate["song_id"]
        if song_id in exclude_song_ids:
            continue

        candidate_release_year = candidate.get("release_year") or _candidate_release_year(candidate)
        candidate["release_year"] = candidate_release_year
        match_signals = _score_candidate_signals(
            candidate=candidate,
            preferred_genres=preferred_genres,
            preferred_artists=preferred_artists,
            free_text=free_text,
            context=context,
            target_year=target_year,
        )
        candidate["match_signals"] = match_signals
        candidate["priority_score"] = _calculate_priority_score(
            candidate,
            match_signals,
            preferred_genres=preferred_genres,
            preferred_artists=preferred_artists,
            free_text=free_text,
            context=context,
        )
        candidate_pool.append(candidate)

    candidate_pool.sort(
        key=lambda item: (
            item.get("priority_score", 0.0),
            item.get("match_signals", {}).get("era", 0.0),
            item.get("match_signals", {}).get("genre", 0.0),
            item.get("match_signals", {}).get("artist", 0.0),
            item.get("match_signals", {}).get("text", 0.0),
            item.get("match_signals", {}).get("feedback", 0.0),
        ),
        reverse=True,
    )

    normalized_pool = candidate_pool[:CANDIDATE_POOL_SIZE]
    return {
        "candidate_pool": normalized_pool,
        "candidate_pool_source_count": len(source_items),
        "candidate_pool_count": len(normalized_pool),
        "expanded_preferred_genres": preferred_genres,
        "expanded_preferred_artists": preferred_artists,
        "preference_expansion": expanded_preferences,
    }


def llm_select_20_candidates(
    state: RecommendationSessionState,
    selector: UpstageCandidateSelectorClient | None = None,
) -> dict[str, Any]:
    candidate_pool = state.get("candidate_pool", [])
    if not candidate_pool:
        raise ValueError("candidate_pool이 비어 있어 LLM 후보 선택을 실행할 수 없습니다.")

    if selector is None and os.environ.get("AI_SKIP_LLM_SELECTION", "").strip().lower() in {"1", "true", "yes"}:
        top = candidate_pool[:20]
        return {
            "selected_candidates": [
                {**c, "selection_reason": "우선순위 점수 기반 자동 선택", "selection_order": i}
                for i, c in enumerate(top, start=1)
            ]
        }

    selector = selector or UpstageCandidateSelectorClient()
    selector_state = dict(state)
    expanded_genres = list(state.get("expanded_preferred_genres") or [])
    expanded_artists = list(state.get("expanded_preferred_artists") or [])
    if expanded_genres:
        selector_state["preferred_genres"] = expanded_genres
    if expanded_artists:
        selector_state["preferred_artists"] = expanded_artists
    try:
        selection = selector.select_candidates_from_state(selector_state)
    except Exception:
        selection = {
            "selected_song_ids": [
                str(candidate["song_id"])
                for candidate in candidate_pool[:20]
                if candidate.get("song_id")
            ],
            "selection_reasons": {},
        }

    candidate_index = {
        candidate.get("song_id", ""): candidate
        for candidate in candidate_pool
        if candidate.get("song_id")
    }
    selected_candidates: list[dict[str, Any]] = []
    for order, song_id in enumerate(selection["selected_song_ids"], start=1):
        candidate = candidate_index.get(song_id)
        if candidate is None:
            raise ValueError(f"후보 풀에 없는 song_id가 선택되었습니다: {song_id}")
        selected_candidate = dict(candidate)
        selected_candidate["selection_reason"] = selection["selection_reasons"].get(
            song_id,
            _build_score_based_selection_reason(candidate),
        )
        selected_candidate["selection_order"] = order
        selected_candidates.append(selected_candidate)

    return {"selected_candidates": selected_candidates}


def _build_score_based_selection_reason(candidate: dict[str, Any]) -> str:
    title = str(candidate.get("title") or "").strip()
    if title:
        return f"'{title}'은 선호 아티스트와 장르에 잘 맞는 곡입니다."
    return "선호 아티스트와 장르에 잘 맞는 곡입니다."


def verify_with_itunes(
    state: RecommendationSessionState,
    verifier: ItunesSearchClient | None = None,
) -> dict[str, Any]:
    source_candidates = list(state.get("selected_candidates") or state.get("candidate_pool") or [])
    if not source_candidates:
        raise ValueError("검증할 후보가 없습니다.")

    if verifier is None and os.environ.get("AI_SKIP_ITUNES_VERIFICATION", "").strip().lower() in {"1", "true", "yes"}:
        verified_candidates = [_enrich_candidate_from_existing_data(candidate) for candidate in source_candidates]
        return {"verified_candidates": verified_candidates}

    verifier = verifier or ItunesSearchClient()
    verified_candidates: list[dict[str, Any]] = []
    for candidate in source_candidates:
        song = _song_from_candidate(candidate)
        if song is None:
            continue
        try:
            verification = verifier.verify(song)
        except Exception:
            continue
        if verification is None:
            continue

        enriched_candidate = dict(candidate)
        enriched_candidate["preview_url"] = verification.track.preview_url
        enriched_candidate["album_art_url"] = verification.track.artwork_url
        enriched_candidate["itunes_track_id"] = verification.track.track_id
        enriched_candidate["itunes_matched_by"] = verification.matched_by
        verified_candidates.append(enriched_candidate)

    if not verified_candidates:
        verified_candidates = [
            _enrich_candidate_from_existing_data(candidate)
            for candidate in source_candidates
        ]

    return {"verified_candidates": verified_candidates}


def select_final_5(state: RecommendationSessionState) -> dict[str, Any]:
    source_candidates = list(state.get("verified_candidates") or state.get("selected_candidates") or [])
    if not source_candidates:
        raise ValueError("최종 5곡을 고를 검증 후보가 없습니다.")

    unique_candidates = _deduplicate_candidates(source_candidates)
    final_candidates: list[dict[str, Any]] = []
    for order, candidate in enumerate(unique_candidates[:FINAL_BUNDLE_SIZE], start=1):
        signals = candidate.get("match_signals") or {}
        final_candidates.append({
            "song_id": candidate.get("song_id", ""),
            "title": candidate.get("title", ""),
            "artists": list(candidate.get("artists") or []),
            "album": candidate.get("album", ""),
            "album_art_url": candidate.get("album_art_url", ""),
            "preview_url": candidate.get("preview_url", ""),
            "slot_type": candidate.get("slot_type") or ("anchor" if order == 1 else "discovery"),
            "reason": candidate.get("selection_reason") or candidate.get("reason") or _build_final_reason(candidate, order),
            "score_breakdown": {
                "era": round(signals.get("era", 0.0), 4),
                "genre": round(signals.get("genre", 0.0), 4),
                "artist": round(signals.get("artist", 0.0), 4),
                "text": round(signals.get("text", 0.0), 4),
                "feedback": round(signals.get("feedback", 0.0), 4),
                "final": round(candidate.get("priority_score", 0.0), 4),
            },
        })

    return {
        "final_bundle": final_candidates,
        "next_action": "collect_feedback",
    }


def _load_candidate_source_items(state: RecommendationSessionState) -> list[Any]:
    for key in ("candidate_source", "catalog", "catalog_candidates", "source_candidates", "songs", "song_catalog"):
        value = state.get(key)
        if isinstance(value, list) and value:
            return list(value)

    catalog_path = state.get("catalog_path")
    if isinstance(catalog_path, str) and catalog_path.strip():
        return load_songs(catalog_path)

    return []


def _expand_preferences(
    state: RecommendationSessionState,
    *,
    preference_expander: UpstagePreferenceExpanderClient | None,
    preferred_genres: list[str],
    preferred_artists: list[str],
) -> PreferenceExpansionOutput:
    if not preferred_genres and not preferred_artists:
        return {
            "expanded_preferred_genres": [],
            "expanded_preferred_artists": [],
            "genre_expansions": {},
            "artist_expansions": {},
        }

    if preference_expander is None and os.environ.get("AI_SKIP_PREFERENCE_EXPANSION", "").strip().lower() in {"1", "true", "yes"}:
        normalized_genres = normalize_expanded_preferences(preferred_genres)
        normalized_artists = normalize_expanded_preferences(preferred_artists)
        return {
            "expanded_preferred_genres": normalized_genres,
            "expanded_preferred_artists": normalized_artists,
            "genre_expansions": {genre: [genre] for genre in normalized_genres},
            "artist_expansions": {artist: [artist] for artist in normalized_artists},
        }

    expander = preference_expander or UpstagePreferenceExpanderClient()
    print(f"[Recommender] preference_expansion 시작 — genres={preferred_genres}, artists={preferred_artists}")
    try:
        expansion = expander.expand_preferences(
            {
                "preferred_genres": preferred_genres,
                "preferred_artists": preferred_artists,
                "age": state.get("age"),
                "preferred_year_center": state.get("preferred_year_center"),
                "free_text": state.get("free_text", ""),
                "context_text": state.get("context_text", ""),
            }
        )
        print(f"[Recommender] preference_expansion 완료 — expanded_genres={expansion.get('expanded_preferred_genres')}, expanded_artists={expansion.get('expanded_preferred_artists')}")
    except Exception as e:
        print(f"[Recommender] preference_expansion 실패 (폴백) — {e}")
        return {
            "expanded_preferred_genres": normalize_expanded_preferences(preferred_genres),
            "expanded_preferred_artists": normalize_expanded_preferences(preferred_artists),
            "genre_expansions": {genre: [genre] for genre in preferred_genres},
            "artist_expansions": {artist: [artist] for artist in preferred_artists},
        }

    expanded_genres = normalize_expanded_preferences(expansion.get("expanded_preferred_genres", []))
    expanded_artists = normalize_expanded_preferences(expansion.get("expanded_preferred_artists", []))
    genre_expansions = {
        key: normalize_expanded_preferences(value)
        for key, value in expansion.get("genre_expansions", {}).items()
    }
    artist_expansions = {
        key: normalize_expanded_preferences(value)
        for key, value in expansion.get("artist_expansions", {}).items()
    }
    if not expanded_genres:
        expanded_genres = normalize_expanded_preferences(preferred_genres)
    if not expanded_artists:
        expanded_artists = normalize_expanded_preferences(preferred_artists)
    if not genre_expansions:
        genre_expansions = {genre: [genre] for genre in preferred_genres}
    if not artist_expansions:
        artist_expansions = {artist: [artist] for artist in preferred_artists}
    return {
        "expanded_preferred_genres": expanded_genres,
        "expanded_preferred_artists": expanded_artists,
        "genre_expansions": genre_expansions,
        "artist_expansions": artist_expansions,
    }


def _candidate_record_from_item(item: Any) -> CandidateRecord | None:
    if isinstance(item, Song):
        return {
            "song_id": item.song_id,
            "title": item.title,
            "artists": [artist.name for artist in item.artists if artist.name],
            "album": item.album.name,
            "release_date": item.release_date,
            "release_year": release_year(item),
            "genres": list(item.genres),
            "like_count": int(item.like_count),
            "lyrics": item.lyrics,
            "chart_appearances": list(item.chart_appearances),
            "source_urls": dict(item.source_urls),
        }

    if isinstance(item, dict):
        song_id = str(item.get("song_id") or item.get("songId") or "").strip()
        title = str(item.get("title") or "").strip()
        if not song_id or not title:
            return None

        artists = _extract_artist_names(item.get("artists", []))
        album = item.get("album") or {}
        if isinstance(album, dict):
            album_name = str(album.get("name") or "").strip()
        else:
            album_name = str(album or "").strip()
        release_date = item.get("release_date") or item.get("releaseDate")
        candidate: CandidateRecord = {
            "song_id": song_id,
            "title": title,
            "artists": artists,
            "album": album_name,
            "release_date": release_date,
            "release_year": item.get("release_year") or item.get("releaseYear"),
            "genres": [str(genre).strip() for genre in item.get("genres", []) if str(genre).strip()],
            "like_count": int(item.get("like_count") or item.get("likeCount") or 0),
            "lyrics": str(item.get("lyrics") or ""),
            "chart_appearances": list(item.get("chart_appearances") or item.get("chartAppearances") or []),
            "source_urls": dict(item.get("source_urls") or item.get("sourceUrls") or {}),
        }
        for key in ("preview_url", "album_art_url", "itunes_track_id", "itunes_matched_by"):
            if key in item:
                candidate[key] = item[key]
        return candidate

    return None


def _song_from_candidate(candidate: dict[str, Any]) -> Song | None:
    song_id = str(candidate.get("song_id") or "").strip()
    title = str(candidate.get("title") or "").strip()
    if not song_id or not title:
        return None

    artists = [
        Artist(name=str(artist).strip())
        for artist in candidate.get("artists", [])
        if str(artist).strip()
    ]
    album = Album(name=str(candidate.get("album") or "").strip())
    return Song(
        song_id=song_id,
        title=title,
        artists=artists,
        album=album,
        release_date=str(candidate.get("release_date") or "").strip() or None,
        genres=[str(genre).strip() for genre in candidate.get("genres", []) if str(genre).strip()],
        like_count=int(candidate.get("like_count") or 0),
        lyrics=str(candidate.get("lyrics") or ""),
        chart_appearances=list(candidate.get("chart_appearances") or []),
        source_urls=dict(candidate.get("source_urls") or {}),
    )


def _enrich_candidate_from_existing_data(candidate: dict[str, Any]) -> dict[str, Any]:
    enriched_candidate = dict(candidate)
    enriched_candidate.setdefault("preview_url", str(enriched_candidate.get("preview_url") or ""))
    enriched_candidate.setdefault("album_art_url", str(enriched_candidate.get("album_art_url") or ""))
    enriched_candidate.setdefault("itunes_track_id", 0)
    enriched_candidate.setdefault("itunes_matched_by", "skip_verification")
    return enriched_candidate


def _deduplicate_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, tuple[str, ...]]] = set()
    unique_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        title = _normalize_text(str(candidate.get("title") or ""))
        artists = tuple(sorted(_normalize_text(str(artist)) for artist in candidate.get("artists", []) if str(artist).strip()))
        signature = (title, artists)
        if signature in seen:
            continue
        seen.add(signature)
        unique_candidates.append(candidate)
    return unique_candidates


def _build_final_reason(candidate: dict[str, Any], order: int) -> str:
    selection_reason = str(candidate.get("selection_reason") or "").strip()
    if selection_reason:
        return selection_reason

    title = str(candidate.get("title") or "").strip()
    if order == 1 and title:
        return f"'{title}'을 시작으로 전체 분위기를 잡는 곡입니다."
    if title:
        return f"'{title}'은 검증을 통과하고 중간 흐름에서 자연스럽게 이어지는 곡입니다."
    return "검증을 통과한 곡입니다."


def _extract_artist_names(raw_artists: Any) -> list[str]:
    if not isinstance(raw_artists, list):
        return []
    artists: list[str] = []
    for item in raw_artists:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("artist_name") or "").strip()
        else:
            name = str(item).strip()
        if name:
            artists.append(name)
    return artists


def _candidate_release_year(candidate: CandidateRecord) -> int | None:
    release_date = candidate.get("release_date")
    if isinstance(release_date, str):
        match = re.search(r"\d{4}", release_date)
        if match:
            return int(match.group(0))
    years = [
        int(appearance["year"])
        for appearance in candidate.get("chart_appearances", [])
        if isinstance(appearance, dict) and str(appearance.get("year", "")).isdigit()
    ]
    return min(years) if years else None


def _target_year_from_state(state: RecommendationSessionState) -> float | None:
    if state.get("preferred_year_center") is not None:
        return float(state["preferred_year_center"])
    if state.get("age") is not None:
        return preferred_year_center_from_age(int(state["age"]))
    return None


def _score_candidate_signals(
    candidate: CandidateRecord,
    preferred_genres: list[str],
    preferred_artists: list[str],
    free_text: str,
    context: dict[str, Any],
    target_year: float | None,
) -> dict[str, float]:
    era = _score_era(candidate.get("release_year"), target_year)
    genre = _score_genre(candidate.get("genres", []), preferred_genres)
    artist = _score_artist(candidate.get("artists", []), preferred_artists, genre)
    text = _score_text(candidate, free_text, context)
    feedback = _score_feedback(candidate, context)
    return {
        "era": era,
        "genre": genre,
        "artist": artist,
        "text": text,
        "feedback": feedback,
        "priority": 0.0,
    }


def _calculate_priority_score(
    candidate: CandidateRecord,
    match_signals: dict[str, float],
    *,
    preferred_genres: list[str],
    preferred_artists: list[str],
    free_text: str,
    context: dict[str, Any],
) -> float:
    active_weights = _active_signal_weights(
        has_genre=bool(preferred_genres),
        has_artist=bool(preferred_artists),
        has_text=bool(str(free_text).strip() or str(context.get("text", "")).strip() or str(context.get("follow_up_text", "")).strip()),
        has_feedback=bool(context.get("songs")),
    )
    penalty = _feedback_penalty(candidate, context)
    priority = sum(match_signals[key] * weight for key, weight in active_weights.items()) - penalty
    return round(priority, 6)


def _active_signal_weights(
    *,
    has_genre: bool,
    has_artist: bool,
    has_text: bool,
    has_feedback: bool,
) -> dict[str, float]:
    weights = {"era": 0.25}
    if has_genre:
        weights["genre"] = 0.25
    if has_artist:
        weights["artist"] = 0.35
    if has_text:
        weights["text"] = 0.10
    if has_feedback:
        weights["feedback"] = 0.10
    total = sum(weights.values())
    if total <= 0:
        return {"era": 1.0}
    return {key: value / total for key, value in weights.items()}


def _score_era(release_year_value: int | None, target_year: float | None) -> float:
    if release_year_value is None or target_year is None:
        return 0.0
    distance = abs(release_year_value - target_year)
    return max(0.0, 1.0 - min(distance, 3.0) / 3.0)


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().strip().split())


def _genre_bucket(value: str) -> str:
    normalized = _normalize_text(value)
    return GENRE_ALIAS_LOOKUP.get(normalized, normalized)


def _score_genre(candidate_genres: list[str], preferred_genres: list[str]) -> float:
    if not preferred_genres or not candidate_genres:
        return 0.0

    candidate_buckets = {_genre_bucket(genre) for genre in candidate_genres if genre.strip()}
    preferred_buckets = {_genre_bucket(genre) for genre in preferred_genres if genre.strip()}
    if candidate_buckets & preferred_buckets:
        return 1.0

    candidate_tokens = {_normalize_text(genre) for genre in candidate_genres if genre.strip()}
    preferred_tokens = {_normalize_text(genre) for genre in preferred_genres if genre.strip()}
    if any(
        pref in candidate
        or candidate in pref
        or pref.replace(" ", "") in candidate.replace(" ", "")
        or candidate.replace(" ", "") in pref.replace(" ", "")
        for pref in preferred_tokens
        for candidate in candidate_tokens
    ):
        return 0.7

    return 0.0


def _score_artist(candidate_artists: list[str], preferred_artists: list[str], genre_score: float) -> float:
    if not preferred_artists or not candidate_artists:
        return 0.0

    candidate_names = {_normalize_text(artist) for artist in candidate_artists if artist.strip()}
    preferred_names = {_normalize_text(artist) for artist in preferred_artists if artist.strip()}
    if candidate_names & preferred_names:
        return 1.0

    if any(
        pref in candidate
        or candidate in pref
        or pref.replace(" ", "") in candidate.replace(" ", "")
        or candidate.replace(" ", "") in pref.replace(" ", "")
        for pref in preferred_names
        for candidate in candidate_names
    ):
        return 0.75

    return 0.0


def _candidate_text(candidate: CandidateRecord) -> str:
    parts = [
        candidate.get("title", ""),
        " ".join(candidate.get("artists", [])),
        candidate.get("album", ""),
        " ".join(candidate.get("genres", [])),
        candidate.get("lyrics", ""),
        candidate.get("selection_reason", ""),
    ]
    return " ".join(part for part in parts if part)


def _score_text(candidate: CandidateRecord, free_text: str, context: dict[str, Any]) -> float:
    query_text = " ".join(
        part
        for part in [
            free_text,
            str(context.get("text", "")),
            str(context.get("follow_up_text", "")),
        ]
        if part
    )
    query_tokens = _tokenize(query_text)
    if not query_tokens:
        return 0.0

    candidate_tokens = _tokenize(_candidate_text(candidate))
    overlap = query_tokens & candidate_tokens
    return min(1.0, len(overlap) / max(1, min(len(query_tokens), 8)))


def _score_feedback(candidate: CandidateRecord, context: dict[str, Any]) -> float:
    songs = context.get("songs", [])
    if not isinstance(songs, list) or not songs:
        return 0.0

    candidate_title = _normalize_text(candidate.get("title", ""))
    candidate_artists = {_normalize_text(artist) for artist in candidate.get("artists", []) if artist.strip()}
    liked_score = 0.0
    disliked_penalty = 0.0

    for item in songs:
        if not isinstance(item, dict):
            continue
        reaction = str(item.get("reaction") or "").strip()
        liked_title = _normalize_text(str(item.get("title") or ""))
        liked_artists = {_normalize_text(artist) for artist in item.get("artists", []) if str(artist).strip()}
        same_artist = bool(candidate_artists & liked_artists)
        same_title = bool(candidate_title and candidate_title == liked_title)
        if reaction == "좋아요" and (same_artist or same_title):
            liked_score = max(liked_score, 1.0)
        if reaction == "싫어요" and (same_artist or same_title):
            disliked_penalty = max(disliked_penalty, 1.0)

    if disliked_penalty > 0.0:
        return 0.0
    return liked_score


def _feedback_penalty(candidate: CandidateRecord, context: dict[str, Any]) -> float:
    songs = context.get("songs", [])
    if not isinstance(songs, list) or not songs:
        return 0.0

    candidate_title = _normalize_text(candidate.get("title", ""))
    candidate_artists = {_normalize_text(artist) for artist in candidate.get("artists", []) if artist.strip()}
    for item in songs:
        if not isinstance(item, dict):
            continue
        reaction = str(item.get("reaction") or "").strip()
        if reaction != "싫어요":
            continue
        disliked_title = _normalize_text(str(item.get("title") or ""))
        disliked_artists = {_normalize_text(artist) for artist in item.get("artists", []) if str(artist).strip()}
        if candidate_title and candidate_title == disliked_title:
            return 0.35
        if candidate_artists & disliked_artists:
            return 0.35
    return 0.0


def _tokenize(text: str) -> set[str]:
    return {token for token in re.split(r"[^0-9A-Za-z가-힣]+", _normalize_text(text)) if token}
