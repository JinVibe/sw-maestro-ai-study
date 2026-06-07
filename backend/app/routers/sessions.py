from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_sessions
from app.schemas import CreateSessionRequest, SessionResponse
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
