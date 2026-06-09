from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_sessions
from app.schemas import CreateSessionRequest, FollowUpRequest, FollowUpResponse, SessionResponse
from app.session_store import SessionStore

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse)
def create_session(
    body: CreateSessionRequest,
    store: SessionStore = Depends(get_sessions),
) -> SessionResponse:
    """온보딩: 나이/선호 장르/선호 아티스트를 받아 세션을 만든다."""
    session = store.create(
        user_id=body.user_id,
        age=body.age,
        preferred_genres=body.preferred_genres,
        preferred_artists=body.preferred_artists,
    )
    return SessionResponse(
        session_id=session.session_id,
        user_id=session.user_id,
        age=session.age,
        preferred_genres=session.preferred_genres,
        preferred_artists=session.preferred_artists,
        next_action=session.next_action,
    )


@router.post("/{session_id}/follow-up", response_model=FollowUpResponse)
def submit_follow_up(
    session_id: str,
    body: FollowUpRequest,
    store: SessionStore = Depends(get_sessions),
) -> FollowUpResponse:
    """싫어요 3개 이상 후 팔로업 텍스트를 저장하고 다음 액션을 반환한다."""
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    session.follow_up_text = body.text
    session.next_action = "recommend_next_bundle"
    return FollowUpResponse(next_action=session.next_action)
