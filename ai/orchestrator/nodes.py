from __future__ import annotations

"""오케스트레이터 노드 모음.

이 파일은 그래프의 흐름 제어와 사용자 피드백 정리에 집중하고,
실제 추천 계산은 `ai.recommender.engine`으로 위임한다.
"""

from typing import Any

from ..recommender.feedback import count_negative_feedbacks
from ..recommender.engine import (
    CANDIDATE_POOL_SIZE,
    FINAL_BUNDLE_SIZE,
    CandidateRecord,
    CandidateSelector,
    build_candidate_pool as recommender_build_candidate_pool,
    llm_select_20_candidates as recommender_llm_select_20_candidates,
    select_final_5 as recommender_select_final_5,
    verify_with_itunes as recommender_verify_with_itunes,
)
from .feedback_sanitizer import (
    extract_feedback_songs,
    feedback_from_song,
    merge_exclude_song_ids,
    sanitize_context,
)
from .state import NextAction, RecommendationSessionState


def ingest_context(state: RecommendationSessionState) -> dict[str, Any]:
    """프론트에서 온 기본 정보를 세션 상태로 정리한다."""

    context = sanitize_context(state.get("context"))
    preferred_genres = _normalize_string_list(state.get("preferred_genres", []))
    preferred_artists = _normalize_string_list(state.get("preferred_artists", []))
    exclude_song_ids = _normalize_string_list(state.get("exclude_song_ids", []))
    follow_up_text = str(state.get("follow_up_text") or "").strip()
    free_text = str(state.get("free_text") or "").strip()
    context_text = str(state.get("context_text") or "").strip()

    return {
        "user_id": str(state.get("user_id") or "").strip(),
        "session_id": str(state.get("session_id") or "").strip(),
        "age": state.get("age"),
        "preferred_genres": preferred_genres,
        "preferred_artists": preferred_artists,
        "free_text": free_text,
        "context": context,
        "context_text": context_text,
        "follow_up_text": follow_up_text,
        "exclude_song_ids": exclude_song_ids,
        "catalog_path": str(state.get("catalog_path") or "").strip(),
        "catalog": list(state.get("catalog") or []),
        "candidate_source": list(state.get("candidate_source") or []),
        "expanded_preferred_genres": list(state.get("expanded_preferred_genres") or []),
        "expanded_preferred_artists": list(state.get("expanded_preferred_artists") or []),
        "preference_expansion": dict(state.get("preference_expansion") or {}),
        "negative_count": int(state.get("negative_count") or 0),
        "next_action": str(state.get("next_action") or "recommend_next_bundle"),
    }


def build_candidate_pool(
    state: RecommendationSessionState,
    preference_expander: Any | None = None,
) -> dict[str, Any]:
    return recommender_build_candidate_pool(state, preference_expander=preference_expander)


def llm_select_20_candidates(
    state: RecommendationSessionState,
    selector: Any | None = None,
) -> dict[str, Any]:
    return recommender_llm_select_20_candidates(state, selector=selector)


def verify_with_itunes(
    state: RecommendationSessionState,
    verifier: Any | None = None,
) -> dict[str, Any]:
    return recommender_verify_with_itunes(state, verifier=verifier)


def select_final_5(state: RecommendationSessionState) -> dict[str, Any]:
    return recommender_select_final_5(state)


def collect_feedback(state: RecommendationSessionState) -> dict[str, Any]:
    """현재 번들에 대한 피드백을 정리하고 다음 추천에 쓸 제외 목록을 만든다."""

    feedback_songs = extract_feedback_songs(state)
    if not feedback_songs:
        raise ValueError("정리할 피드백이 없습니다.")

    feedbacks = [feedback_from_song(song) for song in feedback_songs]
    negative_count = count_negative_feedbacks(feedbacks)
    exclude_song_ids = merge_exclude_song_ids(
        _normalize_string_list(state.get("exclude_song_ids", [])),
        [feedback.song_id for feedback in feedbacks],
    )

    return {
        "context": sanitize_context(state.get("context")),
        "negative_count": negative_count,
        "exclude_song_ids": exclude_song_ids,
    }


def decide_next_action(state: RecommendationSessionState) -> dict[str, Any]:
    """피드백 결과를 보고 다음 행동을 결정한다."""

    negative_count = int(state.get("negative_count") or 0)
    follow_up_text = str(state.get("follow_up_text") or "").strip()

    if negative_count >= 3 and not follow_up_text:
        next_action: NextAction = "request_follow_up_text"
    else:
        next_action = "recommend_next_bundle"

    return {"next_action": next_action}


def route_after_feedback(state: RecommendationSessionState) -> NextAction:
    """결정된 다음 행동을 그래프 분기 값으로 돌려준다."""

    next_action = state.get("next_action") or "recommend_next_bundle"
    return next_action  # type: ignore[return-value]


def _normalize_string_list(values: list[Any]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized
