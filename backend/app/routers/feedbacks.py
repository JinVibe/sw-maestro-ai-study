from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_orchestrator, get_sessions
from app.orchestrator_service import OrchestratorService
from app.schemas import FeedbackRequest, FeedbackResponse
from app.session_store import SessionStore

router = APIRouter(prefix="/feedbacks", tags=["feedbacks"])


@router.post("", response_model=FeedbackResponse)
def submit_feedback(
    body: FeedbackRequest,
    service: OrchestratorService = Depends(get_orchestrator),
    store: SessionStore = Depends(get_sessions),
) -> FeedbackResponse:
    session = store.get(body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    # 피드백을 오케스트레이터가 읽는 context 형태로 만든다.
    feedback_context = {
        "bundle_id": body.bundle_id or session.last_bundle_id,
        "songs": [item.model_dump() for item in body.feedbacks],
        "feedback_summary": {"comment": body.comment} if body.comment else {},
    }
    state = session.to_state(free_text="")
    state["context"] = feedback_context
    state["final_bundle"] = list(session.last_songs.values())

    try:
        updates = service.apply_feedback(state)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # 세션 반영
    session.negative_count = updates.get("negative_count", 0)
    session.exclude_song_ids = updates.get("exclude_song_ids", session.exclude_song_ids)
    session.next_action = updates.get("next_action", session.next_action)
    # 다음 추천에 자동 반영할 피드백 정보 저장
    session.follow_up_text = body.comment
    session.last_feedback_context = updates.get("context") or feedback_context

    # 저장(saved=true) 곡을 보관함에 담기
    saved_ids = {item.song_id for item in body.feedbacks if item.saved}
    existing = {song["song_id"] for song in session.library}
    for song_id in saved_ids:
        song = session.last_songs.get(song_id)
        if song is not None and song_id not in existing:
            session.library.append(song)

    return FeedbackResponse(
        negative_count=session.negative_count,
        next_action=session.next_action,
    )
