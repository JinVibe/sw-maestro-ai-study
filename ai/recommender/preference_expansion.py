from __future__ import annotations

import json
from typing import Any, Literal, TypedDict


class PreferenceExpansionInput(TypedDict, total=False):
    preferred_genres: list[str]
    preferred_artists: list[str]
    age: int
    preferred_year_center: float
    free_text: str
    context_text: str


class PreferenceExpansionOutput(TypedDict):
    expanded_preferred_genres: list[str]
    expanded_preferred_artists: list[str]
    genre_expansions: dict[str, list[str]]
    artist_expansions: dict[str, list[str]]


PromptRole = Literal["system", "user"]


class PromptMessage(TypedDict):
    role: PromptRole
    content: str


def build_preference_expansion_system_prompt() -> str:
    return "\n".join(
        [
            "너는 음악 추천용 선호도 확장기다.",
            "입력된 장르와 아티스트를 반드시 유사 항목으로 확장하라. 원본만 그대로 반환하는 것은 허용되지 않는다.",
            "장르 확장 규칙:",
            "  - 각 장르를 음악적으로 유사하거나 겹치는 장르 2~3개로 확장하라.",
            "  - 예) 발라드 → [발라드, 팝발라드, 어덜트컨템퍼러리]",
            "  - 예) 힙합 → [힙합, R&B, 트랩]",
            "아티스트 확장 규칙:",
            "  - 각 아티스트와 음악 스타일이 유사한 한국 아티스트 2~3명을 추가하라.",
            "  - 예) 아이유 → [아이유, 태연, 백예린]",
            "  - 예) BTS → [BTS, EXO, 세븐틴]",
            "원본 항목은 반드시 첫 번째로 유지하고, 나머지는 유사 항목으로 채워라.",
            "장르는 장르만, 아티스트는 아티스트만 확장하라. 절대 섞지 마라.",
            "불필요한 설명 없이 JSON만 출력하라.",
            '출력 JSON 형식: {"expanded_preferred_genres":["..."],"expanded_preferred_artists":["..."],"genre_expansions":{"원본":["..."]},"artist_expansions":{"원본":["..."]}}',
        ]
    )


def build_preference_expansion_user_prompt(payload: PreferenceExpansionInput) -> str:
    request_payload = {
        "preferred_genres": payload.get("preferred_genres", []),
        "preferred_artists": payload.get("preferred_artists", []),
        "age": payload.get("age"),
        "preferred_year_center": payload.get("preferred_year_center"),
        "free_text": payload.get("free_text", ""),
        "context_text": payload.get("context_text", ""),
    }
    return json.dumps(request_payload, ensure_ascii=False, indent=2)


def build_preference_expansion_messages(payload: PreferenceExpansionInput) -> list[PromptMessage]:
    return [
        {"role": "system", "content": build_preference_expansion_system_prompt()},
        {"role": "user", "content": build_preference_expansion_user_prompt(payload)},
    ]


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


def parse_preference_expansion_output(text: str) -> PreferenceExpansionOutput:
    payload = json.loads(_extract_json_text(text))
    if not isinstance(payload, dict):
        raise ValueError("선호도 확장 결과는 JSON 객체여야 합니다.")

    expanded_preferred_genres = payload.get("expanded_preferred_genres", [])
    expanded_preferred_artists = payload.get("expanded_preferred_artists", [])
    genre_expansions = payload.get("genre_expansions", {})
    artist_expansions = payload.get("artist_expansions", {})

    if not isinstance(expanded_preferred_genres, list) or not all(isinstance(item, str) for item in expanded_preferred_genres):
        raise ValueError("expanded_preferred_genres는 문자열 배열이어야 합니다.")
    if not isinstance(expanded_preferred_artists, list) or not all(isinstance(item, str) for item in expanded_preferred_artists):
        raise ValueError("expanded_preferred_artists는 문자열 배열이어야 합니다.")
    if not isinstance(genre_expansions, dict) or not all(
        isinstance(key, str) and isinstance(value, list) and all(isinstance(item, str) for item in value)
        for key, value in genre_expansions.items()
    ):
        raise ValueError("genre_expansions는 문자열 키와 문자열 배열 값을 가져야 합니다.")
    if not isinstance(artist_expansions, dict) or not all(
        isinstance(key, str) and isinstance(value, list) and all(isinstance(item, str) for item in value)
        for key, value in artist_expansions.items()
    ):
        raise ValueError("artist_expansions는 문자열 키와 문자열 배열 값을 가져야 합니다.")

    return {
        "expanded_preferred_genres": expanded_preferred_genres,
        "expanded_preferred_artists": expanded_preferred_artists,
        "genre_expansions": genre_expansions,
        "artist_expansions": artist_expansions,
    }


def normalize_expanded_preferences(preferences: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for preference in preferences:
        normalized = " ".join(str(preference).strip().split())
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(normalized)
    return unique
