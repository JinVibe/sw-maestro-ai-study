from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_sessions
from app.schemas import LibraryResponse
from app.session_store import SessionStore

router = APIRouter(prefix="/sessions", tags=["library"])


@router.get("/{session_id}/library", response_model=LibraryResponse)
def get_library(
    session_id: str,
    store: SessionStore = Depends(get_sessions),
) -> LibraryResponse:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return LibraryResponse(session_id=session_id, songs=session.library)
