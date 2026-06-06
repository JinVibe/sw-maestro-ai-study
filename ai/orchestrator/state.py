from __future__ import annotations

from typing import Any, Literal, TypedDict


NextAction = Literal[
    "collect_feedback",
    "recommend_next_bundle",
    "request_follow_up_text",
    "finish",
]

Reaction = Literal["\uc88b\uc544\uc694", "\uc2eb\uc5b4\uc694"]


class ContextSongFeedback(TypedDict, total=False):
    song_id: str
    title: str
    artists: list[str]
    reaction: Reaction
    comment: str


class RecommendationContext(TypedDict, total=False):
    bundle_id: str
    songs: list[ContextSongFeedback]


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

    exclude_song_ids: list[str]
    # 가장 최근 번들에서 누적된 싫어요 수입니다.
    negative_count: int
    next_action: NextAction

    candidate_pool: list[dict[str, Any]]
    selected_candidates: list[dict[str, Any]]
    verified_candidates: list[dict[str, Any]]
    final_bundle: list[dict[str, Any]]


DEFAULT_NEXT_ACTION: NextAction = "recommend_next_bundle"
DEFAULT_NEGATIVE_COUNT = 0
