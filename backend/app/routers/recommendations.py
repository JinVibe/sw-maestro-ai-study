from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_orchestrator, get_sessions
from app.orchestrator_service import OrchestratorService
from app.schemas import BundleResponse, RecommendRequest
from app.session_store import SessionStore

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post("", response_model=BundleResponse)
def recommend(
    body: RecommendRequest,
    service: OrchestratorService = Depends(get_orchestrator),
    store: SessionStore = Depends(get_sessions),
) -> BundleResponse:
    session = store.get(body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    state = session.to_state(free_text=body.free_text)

    try:
        bundle = service.recommend(state)
    except ValueError as exc:
        # 후보 부족/입력 오류 등 파이프라인 도메인 에러
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # 상태 갱신: 추천된 곡 보관 + 다음 추천에서 제외
    session.last_bundle_id = bundle["bundle_id"]
    session.last_songs = {}
    for song in bundle["songs"]:
        session.last_songs[song["song_id"]] = song
        if song["song_id"] not in session.exclude_song_ids:
            session.exclude_song_ids.append(song["song_id"])

    return BundleResponse(**bundle)
