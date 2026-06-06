from __future__ import annotations

"""LangGraph 워크플로우용 오케스트레이터 노드 계약입니다.

이 모듈은 얇은 계약층으로 유지합니다. 오케스트레이터 담당자는 함수
시그니처는 그대로 두고 내부 구현만 실제 비즈니스 로직으로 채워 넣으면
됩니다. 추천 모듈은 같은 상태 구조를 계속 사용할 수 있습니다.
"""

from datetime import date
import re
from typing import Any, Callable, TypedDict

from ..recommender import UpstageCandidateSelectorClient
from ..recommender.catalog import load_songs
from ..recommender.era import release_year
from ..recommender.models import Song
from .state import NextAction, RecommendationSessionState


FINAL_BUNDLE_SIZE = 5
CANDIDATE_POOL_SIZE = 50


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
    [RecommendationSessionState, list[CandidateRecord], int],
    list[CandidateRecord],
]


GENRE_ALIAS_GROUPS: dict[str, set[str]] = {
    "발라드": {"발라드", "ballad"},
    "댄스": {"댄스", "dance"},
    "인디": {"인디", "indie"},
    "록": {"록", "rock", "락"},
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


def ingest_context(state: RecommendationSessionState) -> dict[str, Any]:
    # 오케스트레이터 담당자: 세션 입력을 정규화하고 context를 붙인 뒤
    # 다음 그래프 노드가 안전하게 사용할 수 있는 상태로 만들어 주세요.
    raise NotImplementedError("오케스트레이터 담당자가 ingest_context를 구현해야 합니다.")


def llm_select_20_candidates(
    state: RecommendationSessionState,
    selector: UpstageCandidateSelectorClient | None = None,
) -> dict[str, Any]:
    # Upstage LLM으로 후보 20곡을 선택합니다.
    candidate_pool = state.get("candidate_pool", [])
    if not candidate_pool:
        raise ValueError("candidate_pool이 비어 있어서 LLM 후보 선택을 수행할 수 없습니다.")

    selector = selector or UpstageCandidateSelectorClient()
    selection = selector.select_candidates_from_state(state)

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
        selected_candidate["selection_reason"] = selection["selection_reasons"].get(song_id, "")
        selected_candidate["selection_order"] = order
        selected_candidates.append(selected_candidate)

    return {
        "selected_candidates": selected_candidates,
    }


def build_candidate_pool(state: RecommendationSessionState) -> dict[str, Any]:
    # 카탈로그와 세션 맥락을 바탕으로 후보 풀을 점수화합니다.
    source_items = _load_candidate_source_items(state)
    if not source_items:
        raise ValueError("candidate source가 비어 있어서 후보 풀을 만들 수 없습니다.")

    exclude_song_ids = {song_id.strip() for song_id in state.get("exclude_song_ids", []) if song_id.strip()}
    target_year = _target_year_from_state(state)
    preferred_genres = state.get("preferred_genres", [])
    preferred_artists = state.get("preferred_artists", [])
    free_text = state.get("free_text", "")
    context = state.get("context", {})

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
    }


def verify_with_itunes(state: RecommendationSessionState) -> dict[str, Any]:
    # 오케스트레이터 담당자: 미리듣기 불가 곡과 라이브/리마스터 변형을 걸러 주세요.
    raise NotImplementedError("오케스트레이터 담당자가 verify_with_itunes를 구현해야 합니다.")


def select_final_5(state: RecommendationSessionState) -> dict[str, Any]:
    # 오케스트레이터 담당자: 검증이 끝난 곡들 중에서 최종 5곡만 남겨 주세요.
    raise NotImplementedError("오케스트레이터 담당자가 select_final_5를 구현해야 합니다.")


def collect_feedback(state: RecommendationSessionState) -> dict[str, Any]:
    # 오케스트레이터 담당자: 좋아요/싫어요를 집계해서 세션 상태를 갱신해 주세요.
    raise NotImplementedError("오케스트레이터 담당자가 collect_feedback를 구현해야 합니다.")


def decide_next_action(state: RecommendationSessionState) -> dict[str, Any]:
    # 오케스트레이터 담당자: 갱신된 상태를 바탕으로 다음 그래프 분기를 결정해 주세요.
    raise NotImplementedError("오케스트레이터 담당자가 decide_next_action를 구현해야 합니다.")


def route_after_feedback(state: RecommendationSessionState) -> NextAction:
    # 오케스트레이터 담당자: 조건부 엣지에서 사용할 라우트 키를 반환해 주세요.
    raise NotImplementedError("오케스트레이터 담당자가 route_after_feedback를 구현해야 합니다.")


def _load_candidate_source_items(state: RecommendationSessionState) -> list[Any]:
    for key in ("candidate_source", "catalog", "catalog_candidates", "source_candidates", "songs", "song_catalog"):
        value = state.get(key)
        if isinstance(value, list) and value:
            return list(value)

    catalog_path = state.get("catalog_path")
    if isinstance(catalog_path, str) and catalog_path.strip():
        return load_songs(catalog_path)

    return []


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
    if state.get("age") is not None:
        return date.today().year - (state["age"] / 2)
    if state.get("preferred_year_center") is not None:
        return float(state["preferred_year_center"])
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
    weights = {"era": 0.35}
    if has_genre:
        weights["genre"] = 0.20
    if has_artist:
        weights["artist"] = 0.20
    if has_text:
        weights["text"] = 0.15
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

    return 0.35 if genre_score > 0.0 else 0.0


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
