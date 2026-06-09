from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Session:
    """세션/회원별 추천 상태(오케스트레이터 RecommendationSessionState에 매핑).

    백엔드가 요청 사이에 유지하는 값:
      preferred_genres/artists, exclude_song_ids, negative_count, next_action
    """

    session_id: str
    user_id: str = ""
    age: int | None = None
    preferred_genres: list[str] = field(default_factory=list)
    preferred_artists: list[str] = field(default_factory=list)
    exclude_song_ids: list[str] = field(default_factory=list)
    negative_count: int = 0
    next_action: str = "recommend_next_bundle"
    # 마지막 번들(피드백/보관함 재참조): song_id -> song dict
    last_songs: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_bundle_id: str = ""
    library: list[dict[str, Any]] = field(default_factory=list)
    # 피드백에서 추출한 번들 코멘트 — 다음 추천에 자동 반영
    follow_up_text: str = ""
    # 마지막 피드백 context (songs + feedback_summary) — 다음 추천 시 AI에 전달
    last_feedback_context: dict[str, Any] = field(default_factory=dict)

    def to_state(self, free_text: str) -> dict[str, Any]:
        """추천 파이프라인에 넘길 세션 상태 dict를 만든다."""
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "age": self.age,
            "preferred_genres": self.preferred_genres,
            "preferred_artists": self.preferred_artists,
            "free_text": free_text,
            "follow_up_text": self.follow_up_text,
            "context": self.last_feedback_context,
            "exclude_song_ids": list(self.exclude_song_ids),
            "negative_count": self.negative_count,
            "next_action": self.next_action,
        }


class SessionStore:
    """인메모리 세션 저장소. 회원 DB는 같은 인터페이스로 추후 교체."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self, **kwargs: Any) -> Session:
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        session = Session(session_id=session_id, **kwargs)
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)
