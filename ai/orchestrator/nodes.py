from __future__ import annotations

"""오케스트레이터 노드 모음.

이 파일은 그래프의 흐름 제어와 사용자 피드백 정리에 집중하고,
실제 추천 계산은 `ai.recommender.engine`으로 위임한다.
"""

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from ..recommender.feedback import count_negative_feedbacks
from ..recommender.engine import (
    CANDIDATE_POOL_SIZE,
    FINAL_BUNDLE_SIZE,
    CandidateRecord,
    CandidateSelector,
    build_candidate_pool as recommender_build_candidate_pool,
    llm_select_20_candidates as recommender_llm_select_20_candidates,
    select_final_5 as recommender_select_final_5,
    verify_with_itunes as recommender_verify_with_itunes,
)
from .feedback_sanitizer import (
    extract_feedback_songs,
    feedback_from_song,
    merge_exclude_song_ids,
    sanitize_context,
)
from .sheets_client import append_row, get_sheet
from .state import NextAction, RecommendationSessionState

MAX_BUNDLE_RETRY = 2

_VARIANT_PATTERN = re.compile(
    r"\b(live|remaster(ed)?|instrumental|remix|acoustic|karaoke|inst\.?)\b",
    re.IGNORECASE,
)

_SHEET_USER_INPUT = "UserInput"
_SHEET_BUNDLE = "Bundle"
_SHEET_FEEDBACK = "Feedback"

_HEADER_USER_INPUT = ["timestamp", "user_id", "session_id", "age", "preferred_genres", "preferred_artists", "free_text"]
_HEADER_BUNDLE = ["timestamp", "user_id", "session_id", "bundle_id", "emotion_title", "song_ids", "next_action"]
_HEADER_FEEDBACK = ["timestamp", "user_id", "session_id", "bundle_id", "song_id", "title", "artists", "reaction", "bundle_comment"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _save_to_sheet(sheet_name: str, header: list[str], row: list[Any]) -> None:
    try:
        sheet = get_sheet(sheet_name)
        if sheet.row_values(1) != header:
            sheet.insert_row(header, index=1)
        append_row(sheet_name, row)
    except Exception as e:
        print(f"[Orchestrator] 경고: {sheet_name} 시트 저장 실패 — {e}")


# ------------------------------------------------------------------ #
# 노드 함수
# ------------------------------------------------------------------ #

def ingest_context(state: RecommendationSessionState) -> dict[str, Any]:
    """프론트에서 온 기본 정보를 세션 상태로 정리한다."""

    print(f"[Orchestrator] ingest_context — user_id={state.get('user_id')}, session_id={state.get('session_id')}")

    context = sanitize_context(state.get("context"))
    preferred_genres = _normalize_string_list(state.get("preferred_genres", []))
    preferred_artists = _normalize_string_list(state.get("preferred_artists", []))
    exclude_song_ids = _normalize_string_list(state.get("exclude_song_ids", []))
    follow_up_text = str(state.get("follow_up_text") or "").strip()
    if not follow_up_text:
        follow_up_text = str(context.get("feedback_summary", {}).get("comment") or "").strip()
    free_text = str(state.get("free_text") or "").strip()
    context_text = str(state.get("context_text") or "").strip()

    user_id = str(state.get("user_id") or "").strip()
    session_id = str(state.get("session_id") or "").strip()
    age = state.get("age")

    # 온보딩 정보(첫 호출)인 경우에만 시트에 저장
    is_onboarding = not context.get("songs")
    if is_onboarding:
        _save_to_sheet(_SHEET_USER_INPUT, _HEADER_USER_INPUT, [
            _now(), user_id, session_id, age,
            ",".join(preferred_genres),
            ",".join(preferred_artists),
            free_text,
        ])
        print("[Orchestrator] UserInput 시트 저장 완료")

    return {
        "user_id": user_id,
        "session_id": session_id,
        "age": age,
        "preferred_genres": preferred_genres,
        "preferred_artists": preferred_artists,
        "free_text": free_text,
        "context": context,
        "context_text": context_text,
        "follow_up_text": follow_up_text,
        "exclude_song_ids": exclude_song_ids,
        "catalog_path": str(state.get("catalog_path") or "").strip(),
        "catalog": list(state.get("catalog") or []),
        "candidate_source": list(state.get("candidate_source") or []),
        "expanded_preferred_genres": list(state.get("expanded_preferred_genres") or []),
        "expanded_preferred_artists": list(state.get("expanded_preferred_artists") or []),
        "preference_expansion": dict(state.get("preference_expansion") or {}),
        "negative_count": int(state.get("negative_count") or 0),
        "next_action": str(state.get("next_action") or "recommend_next_bundle"),
        "reaction_history": dict(state.get("reaction_history") or {}),
        "outlier_follow_up_question": "",
    }


def build_candidate_pool(
    state: RecommendationSessionState,
    preference_expander: Any | None = None,
) -> dict[str, Any]:
    print(f"[Orchestrator] build_candidate_pool — exclude={state.get('exclude_song_ids', [])}")
    result = recommender_build_candidate_pool(state, preference_expander=preference_expander)
    print(f"[Orchestrator] build_candidate_pool 완료 — 후보 {result.get('candidate_pool_count')}곡 / 소스 {result.get('candidate_pool_source_count')}곡")
    return result


def llm_select_20_candidates(
    state: RecommendationSessionState,
    selector: Any | None = None,
) -> dict[str, Any]:
    print("[Orchestrator] llm_select_20_candidates — LLM 후보 선택 중...")
    result = recommender_llm_select_20_candidates(state, selector=selector)
    print(f"[Orchestrator] llm_select_20_candidates 완료 — {len(result.get('selected_candidates', []))}곡 선택됨")
    return result


def verify_with_itunes(
    state: RecommendationSessionState,
    verifier: Any | None = None,
) -> dict[str, Any]:
    print("[Orchestrator] verify_with_itunes — iTunes 검증 중...")
    result = recommender_verify_with_itunes(state, verifier=verifier)
    print(f"[Orchestrator] verify_with_itunes 완료 — {len(result.get('verified_candidates', []))}곡 통과")
    return result


def select_final_5(state: RecommendationSessionState) -> dict[str, Any]:
    """최종 5곡을 선정하고 번들 검증 + 재요청(최대 2회)을 수행한다."""

    print("[Orchestrator] select_final_5 — 최종 5곡 선정 중...")

    current_state = dict(state)
    songs: list[dict[str, Any]] = []

    for attempt in range(MAX_BUNDLE_RETRY + 1):
        result = recommender_select_final_5(current_state)
        songs = result.get("final_bundle", [])
        errors = _validate_bundle_songs(songs)

        if not errors:
            break

        print(f"[Orchestrator] 번들 검증 실패 (시도 {attempt + 1}/{MAX_BUNDLE_RETRY + 1}) — {errors}")
        if attempt < MAX_BUNDLE_RETRY:
            current_state = {**current_state, "_validation_errors": errors}
            selected = recommender_llm_select_20_candidates(current_state)
            verified = recommender_verify_with_itunes({**current_state, **selected})
            current_state = {**current_state, **selected, **verified}
        else:
            print("[Orchestrator] 최대 재시도 초과 — 현재 결과로 진행")

    bundle_id = f"bundle_{uuid.uuid4().hex[:12]}"
    user_id = str(state.get("user_id") or "")
    session_id = str(state.get("session_id") or "")
    free_text = str(state.get("free_text") or "").strip()
    follow_up_text = str(state.get("follow_up_text") or "").strip()
    emotion_title = _build_emotion_title(free_text, follow_up_text)

    _save_to_sheet(_SHEET_BUNDLE, _HEADER_BUNDLE, [
        _now(), user_id, session_id, bundle_id, emotion_title,
        ",".join(s.get("song_id", "") for s in songs),
        "collect_feedback",
    ])
    print(f"[Orchestrator] Bundle 시트 저장 완료 — bundle_id={bundle_id}")

    titles = [s.get("title", "") for s in songs]
    print(f"[Orchestrator] select_final_5 완료 — {titles}")

    return {
        "final_bundle": songs,
        "bundle_id": bundle_id,
        "emotion_title": emotion_title,
        "next_action": "collect_feedback",
    }


def collect_feedback(state: RecommendationSessionState) -> dict[str, Any]:
    """피드백을 정리하고 이상치를 감지한다."""

    print("[Orchestrator] collect_feedback — 피드백 수집 중...")

    feedback_songs = extract_feedback_songs(state)
    if not feedback_songs:
        raise ValueError("정리할 피드백이 없습니다.")

    feedbacks = [feedback_from_song(song) for song in feedback_songs]
    negative_count = count_negative_feedbacks(feedbacks)
    exclude_song_ids = merge_exclude_song_ids(
        _normalize_string_list(state.get("exclude_song_ids", [])),
        [feedback.song_id for feedback in feedbacks],
    )

    # 이상치 감지
    reaction_history = dict(state.get("reaction_history") or {})
    outlier_question = _detect_outlier(feedback_songs, reaction_history)

    # 반응 기록 업데이트 (다음 번들 상충 감지용)
    for song in feedback_songs:
        reaction = str(song.get("reaction") or "").strip()
        if reaction:
            for artist in song.get("artists", []):
                reaction_history[str(artist)] = reaction

    # Feedback 시트 저장 — final_bundle로 title/artists 보완
    user_id = str(state.get("user_id") or "")
    session_id = str(state.get("session_id") or "")
    bundle_id = str(state.get("bundle_id") or "")
    bundle_comment = str((state.get("context") or {}).get("feedback_summary", {}).get("comment") or "").strip()
    final_bundle_map = {s.get("song_id", ""): s for s in (state.get("final_bundle") or [])}
    ts = _now()
    for song in feedback_songs:
        song_id = song.get("song_id", "")
        meta = final_bundle_map.get(song_id, {})
        title = song.get("title") or meta.get("title", "")
        artists = song.get("artists") or meta.get("artists", [])
        if not isinstance(artists, list):
            artists = []
        _save_to_sheet(_SHEET_FEEDBACK, _HEADER_FEEDBACK, [
            ts, user_id, session_id, bundle_id,
            song_id,
            title,
            ",".join(str(a) for a in artists),
            song.get("reaction", ""),
            bundle_comment,
        ])
    print(f"[Orchestrator] Feedback 시트 저장 완료 — {len(feedback_songs)}곡")

    print(f"[Orchestrator] collect_feedback 완료 — 싫어요 {negative_count}곡, 제외 누적 {len(exclude_song_ids)}곡"
          + (f", 이상치 감지: {outlier_question}" if outlier_question else ""))

    return {
        "context": sanitize_context(state.get("context")),
        "negative_count": negative_count,
        "exclude_song_ids": exclude_song_ids,
        "reaction_history": reaction_history,
        "outlier_follow_up_question": outlier_question,
    }


def decide_next_action(state: RecommendationSessionState) -> dict[str, Any]:
    """피드백 결과를 보고 다음 행동을 결정한다."""

    outlier_question = str(state.get("outlier_follow_up_question") or "").strip()
    negative_count = int(state.get("negative_count") or 0)
    follow_up_text = str(state.get("follow_up_text") or "").strip()

    if outlier_question:
        next_action: NextAction = "request_follow_up_text"
    elif negative_count >= 3 and not follow_up_text:
        next_action = "request_follow_up_text"
    else:
        next_action = "recommend_next_bundle"

    print(f"[Orchestrator] decide_next_action — next_action={next_action} (싫어요={negative_count}, 이상치={bool(outlier_question)})")
    return {"next_action": next_action}


def route_after_feedback(state: RecommendationSessionState) -> NextAction:
    """결정된 다음 행동을 그래프 분기 값으로 돌려준다."""

    next_action = state.get("next_action") or "recommend_next_bundle"
    return next_action  # type: ignore[return-value]


# ------------------------------------------------------------------ #
# emotion_title 생성
# ------------------------------------------------------------------ #

def _build_emotion_title(free_text: str, follow_up_text: str) -> str:
    base = follow_up_text or free_text
    if base:
        return f"'{base}'에 어울리는 추천 묶음"
    return "오늘의 추천 묶음"


# ------------------------------------------------------------------ #
# 번들 검증
# ------------------------------------------------------------------ #

def _validate_bundle_songs(songs: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if len(songs) != FINAL_BUNDLE_SIZE:
        errors.append(f"곡 수 오류: {len(songs)}곡 (기대값 {FINAL_BUNDLE_SIZE}곡)")

    song_ids = [s.get("song_id") for s in songs]
    if len(song_ids) != len(set(song_ids)):
        errors.append("중복 곡 포함")

    for song in songs:
        if not song.get("preview_url"):
            errors.append(f"preview_url 없음: {song.get('title', song.get('song_id'))}")
        if _VARIANT_PATTERN.search(song.get("title", "")):
            errors.append(f"변형 버전 포함: {song.get('title')}")

    return errors


# ------------------------------------------------------------------ #
# 이상치 감지
# ------------------------------------------------------------------ #

def _detect_outlier(songs: list[dict[str, Any]], reaction_history: dict[str, str]) -> str:
    reactions = [str(s.get("reaction") or "") for s in songs]
    dislike_count = reactions.count("싫어요")
    like_count = reactions.count("좋아요")

    # 전체 싫어요 (3곡 이상)
    if dislike_count == len(songs) and len(songs) >= 3:
        return "어떤 분위기의 노래를 원하시나요? 조금 더 알려주시면 더 잘 맞는 곡을 찾아드릴게요."

    # 같은 아티스트 곡 중 한 곡만 싫어요 (편향)
    if dislike_count == 1 and like_count >= 3:
        dislike_song = next((s for s in songs if s.get("reaction") == "싫어요"), None)
        if dislike_song:
            liked_artists = {
                str(a) for s in songs if s.get("reaction") == "좋아요"
                for a in s.get("artists", [])
            }
            if any(str(a) in liked_artists for a in dislike_song.get("artists", [])):
                return "이 아티스트의 곡 중 특별히 피하고 싶은 스타일이 있나요?"

    # 번들 간 상충 피드백
    for song in songs:
        reaction = str(song.get("reaction") or "").strip()
        if not reaction:
            continue
        for artist in song.get("artists", []):
            prev = reaction_history.get(str(artist))
            if prev and prev != reaction:
                return f"'{artist}' 곡에 이전과 다른 반응을 하셨어요. 어떤 스타일의 곡을 원하시나요?"

    return ""


# ------------------------------------------------------------------ #
# 내부 헬퍼
# ------------------------------------------------------------------ #

def _normalize_string_list(values: list[Any]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized
