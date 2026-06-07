"""
Orchestrator

입력 형식 1 — 온보딩 정보:
    {user_id, session_id, age, preferred_genres, preferred_artists, free_text}

입력 형식 2 — 이전 번들 (사용자 반응 포함):
    {bundle_id, songs: [{..., reaction, comment}, ...], ...}

처리 순서:
    1. 입력 형식 판별
    2. 이상치 필터 (의미없는 텍스트, 편향 피드백)
    3. Recommender 요청 JSON 조립
    4. Recommender 호출
    5. 번들 검증 (5곡, preview_url, 변형버전, 중복)
    6. 검증 실패 시 재요청 (최대 2회)
    7. 구글시트 저장
    8. 결과 반환
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Callable

from .context_builder import build_request
from .sheets_client import append_row, get_sheet

MAX_RETRY = 2
BUNDLE_SIZE = 5

_VARIANT_PATTERN = re.compile(
    r"\b(live|remaster(ed)?|instrumental|remix|acoustic|karaoke|inst\.?)\b",
    re.IGNORECASE,
)


# ------------------------------------------------------------------ #
# Orchestrator
# ------------------------------------------------------------------ #

class Orchestrator:
    def __init__(self, recommender_fn: Callable[[dict], dict] | None = None) -> None:
        self._recommend = recommender_fn
        self._onboarding: dict[str, Any] | None = None

    def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        형식 1 (온보딩) 또는 형식 2 (번들) 를 받아 처리한다.
        recommender_fn이 없으면 Recommender 요청 JSON만 반환한다.
        """
        print("\n[Orchestrator] 입력 수신")
        if _is_onboarding(payload):
            print("[Orchestrator] 형식 1 감지 — 온보딩 입력")
            return self._process_onboarding(payload)
        elif _is_bundle(payload):
            print("[Orchestrator] 형식 2 감지 — 번들 입력")
            return self._process_bundle(payload)
        else:
            raise ValueError(f"알 수 없는 입력 형식입니다: {list(payload.keys())}")

    # ------------------------------------------------------------------ #
    # 형식 1 처리
    # ------------------------------------------------------------------ #

    def _process_onboarding(self, onboarding: dict[str, Any]) -> dict[str, Any]:
        self._onboarding = onboarding

        print(f"[Orchestrator] 온보딩 저장 — user_id={onboarding.get('user_id')}, session_id={onboarding.get('session_id')}")
        _save_user_input(onboarding)
        print("[Orchestrator] 구글시트 UserInput 저장 완료")

        print("[Orchestrator] Recommender 요청 JSON 조립 중...")
        request = build_request(onboarding)
        print("[Orchestrator] 요청 JSON 조립 완료")

        if self._recommend is None:
            print("[Orchestrator] Recommender 미연결 — 요청 JSON 반환")
            return request

        return self._call_with_retry(request, onboarding)

    # ------------------------------------------------------------------ #
    # 형식 2 처리
    # ------------------------------------------------------------------ #

    def _process_bundle(self, bundle: dict[str, Any]) -> dict[str, Any]:
        if self._onboarding is None:
            raise RuntimeError("온보딩 정보가 없습니다. 형식 1을 먼저 입력하세요.")

        print(f"[Orchestrator] 이상치 필터 실행 중... (곡 수: {len(bundle.get('songs', []))})")
        filter_result = _filter_outliers(bundle)
        if filter_result["follow_up_required"]:
            print(f"[Orchestrator] 이상치 감지 — follow_up 질문 반환: {filter_result['follow_up_question']}")
            return {
                "next_action": "follow_up",
                "follow_up_question": filter_result["follow_up_question"],
            }
        print("[Orchestrator] 이상치 없음 — 정상 피드백")

        print("[Orchestrator] 구글시트 Feedback 저장 중...")
        _save_feedback(self._onboarding, bundle)
        print("[Orchestrator] Feedback 저장 완료")

        print("[Orchestrator] Recommender 요청 JSON 조립 중 (이전 번들 맥락 포함)...")
        request = build_request(self._onboarding, filter_result["bundle"])
        print(f"[Orchestrator] 요청 JSON 조립 완료 — exclude_song_ids: {request['exclude_song_ids']}, negative_count: {request['negative_count']}")

        if self._recommend is None:
            print("[Orchestrator] Recommender 미연결 — 요청 JSON 반환")
            return request

        return self._call_with_retry(request, self._onboarding)

    # ------------------------------------------------------------------ #
    # Recommender 호출 + 검증 + 재요청
    # ------------------------------------------------------------------ #

    def _call_with_retry(
        self, request: dict[str, Any], onboarding: dict[str, Any]
    ) -> dict[str, Any]:
        last_reasons: list[str] = []
        for attempt in range(MAX_RETRY + 1):
            print(f"[Orchestrator] Recommender 호출 중... (시도 {attempt + 1}/{MAX_RETRY + 1})")
            bundle = self._recommend(request)
            print(f"[Orchestrator] Recommender 응답 수신 — bundle_id: {bundle.get('bundle_id')}")

            print("[Orchestrator] 번들 검증 중... (5곡, preview_url, 변형버전, 중복)")
            result = _validate_bundle(bundle)
            if result["ok"]:
                print("[Orchestrator] 번들 검증 통과")
                print("[Orchestrator] 구글시트 Bundle 저장 중...")
                _save_bundle(onboarding, bundle)
                print("[Orchestrator] Bundle 저장 완료 — 결과 반환")
                return bundle

            print(f"[Orchestrator] 번들 검증 실패 — {result['reasons']}")
            last_reasons = result["reasons"]
            request["_validation_errors"] = last_reasons

        print("[Orchestrator] 최대 재시도 초과 — 오류 반환")
        return {"error": "validation_failed", "reasons": last_reasons}


# ------------------------------------------------------------------ #
# 입력 형식 판별
# ------------------------------------------------------------------ #

def _is_onboarding(payload: dict) -> bool:
    return "user_id" in payload and "bundle_id" not in payload

def _is_bundle(payload: dict) -> bool:
    return "bundle_id" in payload


# ------------------------------------------------------------------ #
# 이상치 필터
# ------------------------------------------------------------------ #

def _filter_outliers(bundle: dict[str, Any]) -> dict[str, Any]:
    songs = bundle.get("songs", [])

    # 코멘트 정제 (의미없는 텍스트 제거)
    cleaned_songs = []
    for s in songs:
        comment = s.get("comment", "").strip()
        if _is_meaningless(comment):
            comment = ""
        cleaned_songs.append({**s, "comment": comment})

    reactions = [s.get("reaction", "") for s in cleaned_songs]
    dislike_count = reactions.count("싫어요")
    like_count = reactions.count("좋아요")

    # 모든 곡 싫어요 → 취향 파악 불가
    if dislike_count == len(songs) and len(songs) >= 3:
        return {
            "follow_up_required": True,
            "follow_up_question": "어떤 분위기의 노래를 원하시나요? 조금 더 알려주시면 더 잘 맞는 곡을 찾아드릴게요.",
            "bundle": {**bundle, "songs": cleaned_songs},
        }

    # 같은 아티스트 곡 중 한 곡만 싫어요 (편향)
    if dislike_count == 1 and like_count >= 3:
        dislike_song = next(s for s in cleaned_songs if s.get("reaction") == "싫어요")
        liked_artists = [a for s in cleaned_songs if s.get("reaction") == "좋아요" for a in s.get("artists", [])]
        if any(a in liked_artists for a in dislike_song.get("artists", [])):
            return {
                "follow_up_required": True,
                "follow_up_question": "이 아티스트의 곡 중 특별히 피하고 싶은 스타일이 있나요?",
                "bundle": {**bundle, "songs": cleaned_songs},
            }

    return {
        "follow_up_required": False,
        "follow_up_question": "",
        "bundle": {**bundle, "songs": cleaned_songs},
    }


def _is_meaningless(text: str) -> bool:
    if not text or len(text) < 2:
        return True
    if re.fullmatch(r"(.)\1{3,}", text):        # ㅋㅋㅋㅋ, aaaa
        return True
    if re.fullmatch(r"[ㄱ-ㅎㅏ-ㅣ\s]+", text):  # 자음/모음만
        return True
    return False


# ------------------------------------------------------------------ #
# 번들 검증
# ------------------------------------------------------------------ #

def _validate_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    songs: list[dict] = bundle.get("songs", [])

    if len(songs) != BUNDLE_SIZE:
        reasons.append(f"곡 수 오류: {len(songs)}곡 (기대값 {BUNDLE_SIZE}곡)")

    song_ids = [s.get("song_id") for s in songs]
    if len(song_ids) != len(set(song_ids)):
        reasons.append("중복 곡 포함")

    for song in songs:
        if not song.get("preview_url"):
            reasons.append(f"preview_url 없음: {song.get('title', song.get('song_id'))}")
        if _VARIANT_PATTERN.search(song.get("title", "")):
            reasons.append(f"변형 버전 포함: {song.get('title')}")

    return {"ok": len(reasons) == 0, "reasons": reasons}


# ------------------------------------------------------------------ #
# 구글시트 저장
# ------------------------------------------------------------------ #

_SHEET_USER_INPUT = "UserInput"
_SHEET_BUNDLE    = "Bundle"
_SHEET_FEEDBACK  = "Feedback"

_HEADER_USER_INPUT = ["timestamp", "user_id", "session_id", "age", "preferred_genres", "preferred_artists", "free_text"]
_HEADER_BUNDLE     = ["timestamp", "user_id", "session_id", "bundle_id", "emotion_title", "song_ids", "next_action"]
_HEADER_FEEDBACK   = ["timestamp", "user_id", "session_id", "bundle_id", "song_id", "title", "artists", "reaction", "comment"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_header(sheet_name: str, header: list[str]) -> None:
    sheet = get_sheet(sheet_name)
    if sheet.row_values(1) != header:
        sheet.insert_row(header, index=1)


def _save_user_input(onboarding: dict[str, Any]) -> None:
    try:
        _ensure_header(_SHEET_USER_INPUT, _HEADER_USER_INPUT)
        append_row(_SHEET_USER_INPUT, [
            _now(),
            onboarding.get("user_id", ""),
            onboarding.get("session_id", ""),
            onboarding.get("age", ""),
            ",".join(onboarding.get("preferred_genres", [])),
            ",".join(onboarding.get("preferred_artists", [])),
            onboarding.get("free_text", ""),
        ])
    except Exception as e:
        print(f"[Orchestrator] 경고: UserInput 시트 저장 실패 — {e}")


def _save_bundle(onboarding: dict[str, Any], bundle: dict[str, Any]) -> None:
    try:
        _ensure_header(_SHEET_BUNDLE, _HEADER_BUNDLE)
        songs = bundle.get("songs", [])
        append_row(_SHEET_BUNDLE, [
            _now(),
            onboarding.get("user_id", ""),
            onboarding.get("session_id", ""),
            bundle.get("bundle_id", ""),
            bundle.get("emotion_title", ""),
            ",".join(s.get("song_id", "") for s in songs),
            bundle.get("next_action", ""),
        ])
    except Exception:
        pass


def _save_feedback(onboarding: dict[str, Any], bundle: dict[str, Any]) -> None:
    try:
        _ensure_header(_SHEET_FEEDBACK, _HEADER_FEEDBACK)
        ts = _now()
        for song in bundle.get("songs", []):
            append_row(_SHEET_FEEDBACK, [
                ts,
                onboarding.get("user_id", ""),
                onboarding.get("session_id", ""),
                bundle.get("bundle_id", ""),
                song.get("song_id", ""),
                song.get("title", ""),
                ",".join(song.get("artists", [])),
                song.get("reaction", ""),
                song.get("comment", ""),
            ])
    except Exception:
        pass
