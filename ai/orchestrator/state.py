from __future__ import annotations

from typing import Any, Literal, TypedDict


NextAction = Literal[
    "collect_feedback",
    "recommend_next_bundle",
    "request_follow_up_text",
    "finish",
]

Reaction = Literal["좋아요", "싫어요"]


class ContextSongFeedback(TypedDict, total=False):
    song_id: str
    title: str
    artists: list[str]
    reaction: Reaction


class RecommendationContext(TypedDict, total=False):
    bundle_id: str
    songs: list[ContextSongFeedback]
    feedback_summary: dict[str, Any]


class RecommendationSessionState(TypedDict, total=False):
    user_id: str
    session_id: str

    age: int
    preferred_genres: list[str]
    preferred_artists: list[str]
    free_text: str

    context: RecommendationContext
    context_text: str
    follow_up_text: str

    # 후보 풀을 만들기 위해 오케스트레이터가 넘겨줄 수 있는 원본 카탈로그 경로입니다.
    catalog_path: str
    # 이미 메모리에 있는 카탈로그 후보입니다.
    catalog: list[dict[str, Any]]
    candidate_source: list[dict[str, Any]]
    expanded_preferred_genres: list[str]
    expanded_preferred_artists: list[str]
    preference_expansion: dict[str, Any]

    exclude_song_ids: list[str]
    # 가장 최근 번들에서 누적된 싫어요 수입니다.
    negative_count: int
    next_action: NextAction

    candidate_pool: list[dict[str, Any]]
    selected_candidates: list[dict[str, Any]]
    verified_candidates: list[dict[str, Any]]
    final_bundle: list[dict[str, Any]]

    candidate_pool_source_count: int
    candidate_pool_count: int

    bundle_id: str
    emotion_title: str
    reaction_history: dict[str, str]      # artist → 마지막 반응 (번들 간 상충 감지용)
    outlier_follow_up_question: str        # 이상치 감지 시 follow-up 질문


DEFAULT_NEXT_ACTION: NextAction = "recommend_next_bundle"
DEFAULT_NEGATIVE_COUNT = 0
