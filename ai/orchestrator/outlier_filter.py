from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .session_context import SongFeedback


@dataclass
class FilterResult:
    feedbacks: list[SongFeedback]
    filtered_comments: list[str]   # 제거된 comment 목록
    follow_up_required: bool       # 추가 확인 질문 필요 여부
    follow_up_reason: str = ""


def filter_feedback(feedbacks: list[SongFeedback]) -> FilterResult:
    """이상치를 감지하고 정리된 피드백을 반환한다."""
    cleaned = _clean_comments(feedbacks)
    filtered_comments = [
        fb_orig.comment
        for fb_orig, fb_clean in zip(feedbacks, cleaned)
        if fb_orig.comment != fb_clean.comment
    ]

    follow_up_required, follow_up_reason = _detect_anomaly(cleaned)
    if follow_up_required:
        cleaned = _normalize_biased(cleaned)

    return FilterResult(
        feedbacks=cleaned,
        filtered_comments=filtered_comments,
        follow_up_required=follow_up_required,
        follow_up_reason=follow_up_reason,
    )


def _clean_comments(feedbacks: list[SongFeedback]) -> list[SongFeedback]:
    """의미 없는 comment를 빈 문자열로 교체한다."""
    result = []
    for fb in feedbacks:
        comment = fb.comment.strip()
        if _is_meaningless(comment):
            comment = ""
        result.append(SongFeedback(
            song_id=fb.song_id,
            title=fb.title,
            artists=fb.artists,
            reaction=fb.reaction,
            comment=comment,
        ))
    return result


def _is_meaningless(text: str) -> bool:
    if not text or len(text) < 2:
        return True
    # 반복 문자 (예: "ㅋㅋㅋㅋ", "aaaa")
    if re.fullmatch(r"(.)\1{3,}", text):
        return True
    # 자음/모음만 있는 텍스트 (예: "ㅋㅋ", "ㅎㅎ")
    if re.fullmatch(r"[ㄱ-ㅎㅏ-ㅣ\s]+", text):
        return True
    return False


def _detect_anomaly(feedbacks: list[SongFeedback]) -> tuple[bool, str]:
    if not feedbacks:
        return False, ""

    reactions = [fb.reaction for fb in feedbacks]
    like_count = reactions.count("좋아요")
    dislike_count = reactions.count("싫어요")

    # 동일 아티스트 곡을 거의 전부 좋아요 후 한 곡만 싫어요
    if dislike_count == 1 and like_count >= 3:
        dislike_fb = next(fb for fb in feedbacks if fb.reaction == "싫어요")
        liked_artists: list[str] = []
        for fb in feedbacks:
            if fb.reaction == "좋아요":
                liked_artists.extend(fb.artists)
        if any(a in liked_artists for a in dislike_fb.artists):
            return True, "같은 아티스트 곡 중 유독 한 곡만 싫어요 처리됨"

    # 전체 다 싫어요 (취향 파악 불가 상태)
    if dislike_count == len(feedbacks) and len(feedbacks) >= 3:
        return True, "모든 곡에 싫어요 — 취향 단서 부족"

    return False, ""


def _normalize_biased(feedbacks: list[SongFeedback]) -> list[SongFeedback]:
    """편향된 피드백에서 싫어요만 유지하고 나머지는 중립 처리한다."""
    return [
        SongFeedback(
            song_id=fb.song_id,
            title=fb.title,
            artists=fb.artists,
            reaction="싫어요" if fb.reaction == "싫어요" else "좋아요",
            comment=fb.comment,
        )
        for fb in feedbacks
    ]
