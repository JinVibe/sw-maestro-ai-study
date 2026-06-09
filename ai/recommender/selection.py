from __future__ import annotations

import json
from typing import Any, Literal, TypedDict

from .era import preferred_year_center_from_age


CANDIDATE_SELECTION_TARGET_SIZE = 20
FINAL_BUNDLE_SIZE = 5


class SelectionSignals(TypedDict, total=False):
    era: float
    genre: float
    artist: float
    text: float
    feedback: float


class SelectionContextSongFeedback(TypedDict, total=False):
    song_id: str
    title: str
    artists: list[str]
    reaction: str


class SelectionContext(TypedDict, total=False):
    bundle_id: str
    songs: list[SelectionContextSongFeedback]


class SelectionCandidate(TypedDict, total=False):
    song_id: str
    title: str
    artists: list[str]
    album: str
    release_year: int | None
    genres: list[str]
    like_count: int
    lyrics_excerpt: str
    match_signals: SelectionSignals


class CandidateSelectionInput(TypedDict, total=False):
    user_id: str
    session_id: str
    age: int
    preferred_year_center: float
    preferred_genres: list[str]
    preferred_artists: list[str]
    free_text: str
    context: SelectionContext
    context_text: str
    follow_up_text: str
    exclude_song_ids: list[str]
    negative_count: int
    candidate_pool: list[SelectionCandidate]
    target_size: int
    final_size: int


class CandidateSelectionOutput(TypedDict):
    selected_song_ids: list[str]
    selection_reasons: dict[str, str]


PromptRole = Literal["system", "user"]


class PromptMessage(TypedDict):
    role: PromptRole
    content: str


def build_candidate_selection_system_prompt() -> str:
    return "\n".join(
        [
            "당신은 음악 추천 후보를 고르는 전문가입니다.",
            "입력으로 받은 후보 풀 안에서만 곡을 골라야 하며, 새로운 곡을 만들어내면 안 됩니다.",
            f"후보 선택 목표는 정확히 {CANDIDATE_SELECTION_TARGET_SIZE}곡입니다.",
            f"이후 단계에서 최종 {FINAL_BUNDLE_SIZE}곡만 사용자에게 전달할 예정이지만, 지금 단계에서는 후보 20곡을 고르는 것이 목표입니다.",
            "우선순위는 다음 순서를 따르세요.",
            "1. 나이 기반 시대 근접성",
            "2. 선호 장르 일치 또는 의미상 유사한 장르",
            "3. 선호 아티스트 일치 또는 의미상 유사한 아티스트/장르",
            "4. free_text와의 의미적 유사도",
            "5. 이전 피드백 반영",
            "동일한 곡의 중복 선택은 금지합니다.",
            "라이브, 리마스터, 인스트루멘탈처럼 변형 버전이 드러나는 후보는 가능하면 피하세요.",
            "출력은 반드시 JSON만 사용하고, 설명 문장은 JSON 바깥에 쓰지 마세요.",
            '출력 JSON 형식은 다음과 같습니다: {"selected_song_ids":["..."],"selection_reasons":{"song_id":"선택 이유"}}',
        ]
    )


def build_candidate_selection_user_prompt(payload: CandidateSelectionInput) -> str:
    request_payload = {
        "user_id": payload.get("user_id", ""),
        "session_id": payload.get("session_id", ""),
        "age": payload.get("age"),
        "preferred_year_center": payload.get("preferred_year_center"),
        "preferred_genres": payload.get("preferred_genres", []),
        "preferred_artists": payload.get("preferred_artists", []),
        "free_text": payload.get("free_text", ""),
        "context_text": payload.get("context_text", ""),
        "follow_up_text": payload.get("follow_up_text", ""),
        "exclude_song_ids": payload.get("exclude_song_ids", []),
        "negative_count": payload.get("negative_count", 0),
        "target_size": payload.get("target_size", CANDIDATE_SELECTION_TARGET_SIZE),
        "final_size": payload.get("final_size", FINAL_BUNDLE_SIZE),
        "context": payload.get("context", {}),
        "candidate_pool": [_slim_candidate(c) for c in payload.get("candidate_pool", [])],
    }
    return json.dumps(request_payload, ensure_ascii=False, indent=2)


def _slim_candidate(candidate: dict) -> dict:
    """LLM에 전달할 후보에서 가사 전문 등 불필요한 대용량 필드를 제거합니다."""
    return {
        "song_id": candidate.get("song_id", ""),
        "title": candidate.get("title", ""),
        "artists": candidate.get("artists", []),
        "album": candidate.get("album", ""),
        "release_year": candidate.get("release_year"),
        "genres": candidate.get("genres", []),
        "like_count": candidate.get("like_count", 0),
        "match_signals": candidate.get("match_signals", {}),
    }


def build_candidate_selection_messages(payload: CandidateSelectionInput) -> list[PromptMessage]:
    return [
        {"role": "system", "content": build_candidate_selection_system_prompt()},
        {"role": "user", "content": build_candidate_selection_user_prompt(payload)},
    ]


def candidate_selection_input_from_state(state: dict[str, Any]) -> CandidateSelectionInput:
    """오케스트레이터 상태를 LLM 후보 선택 입력으로 변환합니다."""

    candidate_pool = state.get("candidate_pool", [])
    preferred_year_center = state.get("preferred_year_center")
    if preferred_year_center is None and state.get("age") is not None:
        # 오케스트레이터가 시대 중심값을 넘기지 않아도 나이로 보조 계산합니다.
        preferred_year_center = preferred_year_center_from_age(state["age"])
    return {
        "user_id": state.get("user_id", ""),
        "session_id": state.get("session_id", ""),
        "age": state.get("age"),
        "preferred_year_center": preferred_year_center,
        "preferred_genres": state.get("preferred_genres", []),
        "preferred_artists": state.get("preferred_artists", []),
        "free_text": state.get("free_text", ""),
        "context": state.get("context", {}),
        "context_text": state.get("context_text", ""),
        "follow_up_text": state.get("follow_up_text", ""),
        "exclude_song_ids": state.get("exclude_song_ids", []),
        "negative_count": state.get("negative_count", 0),
        "candidate_pool": candidate_pool,
        "target_size": state.get("target_size", CANDIDATE_SELECTION_TARGET_SIZE),
        "final_size": state.get("final_size", FINAL_BUNDLE_SIZE),
    }


def _extract_json_text(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        raise ValueError("LLM 응답이 비어 있습니다.")
    try:
        json.loads(stripped)
        return stripped
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            candidate = stripped[start : end + 1]
            json.loads(candidate)
            return candidate
        raise


def parse_candidate_selection_output(text: str) -> CandidateSelectionOutput:
    payload = json.loads(_extract_json_text(text))
    if not isinstance(payload, dict):
        raise ValueError("후보 선택 결과는 JSON 객체여야 합니다.")
    selected_song_ids = payload.get("selected_song_ids")
    selection_reasons = payload.get("selection_reasons", {})
    if not isinstance(selected_song_ids, list) or not all(isinstance(item, str) for item in selected_song_ids):
        raise ValueError("selected_song_ids는 문자열 배열이어야 합니다.")
    if not isinstance(selection_reasons, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in selection_reasons.items()):
        raise ValueError("selection_reasons는 문자열-문자열 맵이어야 합니다.")
    return {
        "selected_song_ids": selected_song_ids,
        "selection_reasons": selection_reasons,
    }


def normalize_candidate_pool(candidate_pool: list[SelectionCandidate]) -> list[SelectionCandidate]:
    """후보 풀에서 song_id 기준 중복을 제거합니다."""

    unique: list[SelectionCandidate] = []
    seen: set[str] = set()
    for candidate in candidate_pool:
        song_id = candidate.get("song_id", "").strip()
        if not song_id or song_id in seen:
            continue
        seen.add(song_id)
        unique.append(candidate)
    return unique
