from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent.parent
RAW_CATALOG = ROOT / "ai/data/raw/melon_kpop_2000_2025.jsonl"


class FakeSelector:
    """네트워크 없이 도는 가짜 LLM 후보 선별기.

    후보 풀 앞에서 5곡을 그대로 골라준다(select_candidates_from_state 계약).
    """

    def select_candidates_from_state(self, state: dict) -> dict:
        pool = state.get("candidate_pool", [])
        ids = [c["song_id"] for c in pool[:5]]
        return {
            "selected_song_ids": ids,
            "selection_reasons": {sid: "테스트 추천 사유" for sid in ids},
        }


@pytest.fixture
def client(monkeypatch):
    # iTunes 검증/선호 확장 LLM 호출 스킵(네트워크/키 없이 구동)
    monkeypatch.setenv("AI_SKIP_ITUNES_VERIFICATION", "1")
    monkeypatch.setenv("AI_SKIP_PREFERENCE_EXPANSION", "1")
    monkeypatch.setenv("AI_SKIP_LLM_SELECTION", "1")

    from app.main import app
    from app.deps import get_orchestrator
    from app.orchestrator_service import OrchestratorService

    fake_service = OrchestratorService(
        catalog_path=RAW_CATALOG,
        selector_factory=FakeSelector,
        expander_factory=None,
        verifier=None,  # AI_SKIP_ITUNES_VERIFICATION=1 이라 실제 호출 안 함
    )
    app.dependency_overrides[get_orchestrator] = lambda: fake_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _create_session(client) -> str:
    resp = client.post(
        "/sessions",
        json={"age": 36, "preferred_genres": ["발라드"], "preferred_artists": ["조성모"]},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["session_id"]


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_full_flow(client):
    session_id = _create_session(client)

    rec = client.post(
        "/recommendations",
        json={"session_id": session_id, "free_text": "밤에 산책할 때 듣고 싶어요"},
    )
    assert rec.status_code == 200, rec.text
    bundle = rec.json()
    assert len(bundle["songs"]) == 5
    assert bundle["next_action"] == "collect_feedback"
    first = bundle["songs"][0]["song_id"]

    fb = client.post(
        "/feedbacks",
        json={
            "session_id": session_id,
            "bundle_id": bundle["bundle_id"],
            "feedbacks": [
                {"song_id": first, "reaction": "좋아요", "saved": True}
            ],
        },
    )
    assert fb.status_code == 200, fb.text
    assert fb.json()["next_action"] == "recommend_next_bundle"

    lib = client.get(f"/sessions/{session_id}/library")
    assert [s["song_id"] for s in lib.json()["songs"]] == [first]


def test_three_dislikes_request_follow_up(client):
    session_id = _create_session(client)
    rec = client.post(
        "/recommendations",
        json={"session_id": session_id, "free_text": "가을 노래"},
    ).json()
    ids = [s["song_id"] for s in rec["songs"]][:3]

    fb = client.post(
        "/feedbacks",
        json={
            "session_id": session_id,
            "feedbacks": [{"song_id": sid, "reaction": "싫어요"} for sid in ids],
        },
    )
    assert fb.json()["negative_count"] == 3
    assert fb.json()["next_action"] == "request_follow_up_text"


def test_recommend_missing_session_404(client):
    resp = client.post("/recommendations", json={"session_id": "nope", "free_text": "x"})
    assert resp.status_code == 404
