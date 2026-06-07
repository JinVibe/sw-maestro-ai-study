"""
Orchestrator 핵심 로직.

입력 형식 1 — 온보딩 정보만:
    {user_id, session_id, age, preferred_genres, preferred_artists, free_text}

입력 형식 2 — 온보딩 정보 + 이전 번들(세션 상태):
    onboarding + bundle {bundle_id, songs, ...}

출력 — Recommender에 전달할 요청 JSON
"""
from __future__ import annotations

import json
from typing import Any


DEFAULT_CATALOG_PATH = "ai/data/samples/melon_kpop_sample.jsonl"


def build_request(
    onboarding: dict[str, Any],
    bundle: dict[str, Any] | None = None,
    catalog_path: str = DEFAULT_CATALOG_PATH,
) -> dict[str, Any]:
    """
    onboarding : 온보딩 입력 (입력 형식 1)
    bundle     : 이전 추천 결과 (입력 형식 2, 없으면 None)
    return     : Recommender에 전달할 요청 JSON
    """
    if bundle is None:
        context, context_text, exclude_ids, negative_count, follow_up_text = _empty_context()
    else:
        context, context_text, exclude_ids, negative_count, follow_up_text = _from_bundle(bundle)

    return {
        "user_id": onboarding["user_id"],
        "session_id": onboarding["session_id"],
        "age": onboarding["age"],
        "preferred_genres": onboarding.get("preferred_genres", []),
        "preferred_artists": onboarding.get("preferred_artists", []),
        "free_text": onboarding.get("free_text", ""),
        "context": context,
        "context_text": context_text,
        "follow_up_text": follow_up_text,
        "exclude_song_ids": exclude_ids,
        "catalog_path": catalog_path,
        "candidate_source": [],
        "expanded_preferred_genres": [],
        "expanded_preferred_artists": [],
        "preference_expansion": {},
        "negative_count": negative_count,
        "next_action": "recommend_next_bundle",
    }


# ------------------------------------------------------------------ #
# 내부 헬퍼
# ------------------------------------------------------------------ #

def _empty_context():
    context = {"bundle_id": "", "songs": [], "feedback_summary": {}}
    return context, "", [], 0, ""


def _from_bundle(bundle: dict[str, Any]):
    songs = bundle.get("songs", [])

    context_songs = [
        {
            "song_id": s["song_id"],
            "title": s["title"],
            "artists": s["artists"],
            "reaction": s.get("reaction", ""),
        }
        for s in songs
    ]

    context = {
        "bundle_id": bundle.get("bundle_id", ""),
        "songs": context_songs,
        "feedback_summary": {},
    }
    context_text = json.dumps(context, ensure_ascii=False)
    exclude_ids = [s["song_id"] for s in songs]
    negative_count = sum(1 for s in songs if s.get("reaction") == "싫어요")
    follow_up_text = " ".join(
        s["comment"] for s in songs if s.get("comment", "").strip()
    ).strip()

    return context, context_text, exclude_ids, negative_count, follow_up_text
