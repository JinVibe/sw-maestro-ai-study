from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Callable

from ai.recommender.catalog import load_songs
from ai.recommender.upstage_client import (
    UpstageCandidateSelectorClient,
    UpstagePreferenceExpanderClient,
)
# 추천 파이프라인은 orchestrator 노드 경유로 호출한다(엔진 직접 import 시 순환 발생).
from ai.orchestrator.nodes import (
    build_candidate_pool,
    collect_feedback,
    decide_next_action,
    ingest_context,
    llm_select_20_candidates,
    select_final_5,
    verify_with_itunes,
)

# 응답 곡 dict에 노출할 필드(계약서 3-3 기준).
_SONG_FIELDS = (
    "song_id",
    "title",
    "artists",
    "album",
    "album_art_url",
    "preview_url",
    "slot_type",
    "reason",
)


class OrchestratorService:
    """오케스트레이터 추천 파이프라인을 구동하는 백엔드 서비스.

    계약서(orchestrator-recommender-contract.md)의 흐름을 HTTP 요청/응답 단위로 나눠 실행한다.
      - recommend():  ingest -> build_pool -> llm_select -> verify -> select_final_5 -> 번들 조립
      - apply_feedback(): collect_feedback -> decide_next_action

    LLM/iTunes 클라이언트는 주입 가능하다(운영=Upstage/iTunes, 테스트=가짜).
    """

    def __init__(
        self,
        catalog_path: Path,
        *,
        selector_factory: Callable[[], Any] = UpstageCandidateSelectorClient,
        expander_factory: Callable[[], Any] | None = UpstagePreferenceExpanderClient,
        verifier: Any | None = None,
    ) -> None:
        # 카탈로그(후보 소스)는 서버 시작 시 1회 로드해 재사용한다.
        supplemental_catalog = _load_supplemental_catalog()
        base_catalog = _exclude_duplicate_songs(load_songs(catalog_path), supplemental_catalog)
        self.catalog = [*supplemental_catalog, *base_catalog]
        self._selector_factory = selector_factory
        self._expander_factory = expander_factory
        self._verifier = verifier

    def recommend(self, state: dict[str, Any]) -> dict[str, Any]:
        """1회 추천 턴: 세션 상태 -> 5곡 번들 dict."""
        state = dict(state)
        state.setdefault("candidate_source", self.catalog)

        state.update(ingest_context(state))
        expander = self._expander_factory() if self._expander_factory else None
        state.update(build_candidate_pool(state, preference_expander=expander))
        selector = None if _skip_llm_selection() else self._selector_factory()
        state.update(llm_select_20_candidates(state, selector=selector))
        state.update(verify_with_itunes(state, verifier=self._verifier))
        state.update(select_final_5(state))

        return self._assemble_bundle(state)

    def apply_feedback(self, state: dict[str, Any]) -> dict[str, Any]:
        """피드백 턴: 제외 목록/싫어요 수/다음 액션 갱신값을 돌려준다."""
        state = dict(state)
        updates: dict[str, Any] = {}
        updates.update(collect_feedback(state))
        merged = {**state, **updates}
        updates.update(decide_next_action(merged))
        return updates

    @staticmethod
    def _assemble_bundle(state: dict[str, Any]) -> dict[str, Any]:
        final_bundle = state.get("final_bundle") or []
        songs = []
        for candidate in final_bundle:
            song = {field: candidate.get(field, "") for field in _SONG_FIELDS}
            if not isinstance(song.get("artists"), list):
                song["artists"] = []
            songs.append(song)
        return {
            "bundle_id": state.get("bundle_id") or f"bundle_{uuid.uuid4().hex[:12]}",
            "emotion_title": state.get("emotion_title") or "오늘의 추천 묶음",
            "songs": songs,
            "next_action": state.get("next_action", "collect_feedback"),
        }


def _skip_llm_selection() -> bool:
    return os.environ.get("AI_SKIP_LLM_SELECTION", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _load_supplemental_catalog() -> list[Any]:
    supplement_path = Path(
        os.environ.get(
            "CATALOG_SUPPLEMENT_PATH",
            "ai/data/samples/modern_kpop_supplement.jsonl",
        )
    )
    if not supplement_path.exists():
        return []
    return load_songs(supplement_path)


def _exclude_duplicate_songs(songs: list[Any], priority_songs: list[Any]) -> list[Any]:
    priority_signatures = {
        _song_signature(song)
        for song in priority_songs
        if _song_signature(song) is not None
    }
    return [
        song
        for song in songs
        if _song_signature(song) not in priority_signatures
    ]


def _song_signature(song: Any) -> tuple[str, tuple[str, ...]] | None:
    title = str(getattr(song, "title", "") or "").casefold().strip()
    artists = tuple(
        sorted(
            str(getattr(artist, "name", "") or "").casefold().strip()
            for artist in getattr(song, "artists", [])
            if str(getattr(artist, "name", "") or "").strip()
        )
    )
    if not title:
        return None
    return title, artists
