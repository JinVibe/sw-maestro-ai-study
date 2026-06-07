from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .sheets_client import append_row, read_all_records

USER_INPUT_SHEET = "UserInput"
BUNDLE_SHEET = "Bundle"
FEEDBACK_SHEET = "Feedback"
SONG_CATALOG_SHEET = "SongCatalog"

_USER_INPUT_HEADER = [
    "timestamp", "user_id", "session_id", "age",
    "preferred_genres", "preferred_artists", "free_text",
]
_BUNDLE_HEADER = [
    "timestamp", "user_id", "session_id", "bundle_id",
    "emotion_title", "song_ids", "next_action",
]
_FEEDBACK_HEADER = [
    "timestamp", "user_id", "session_id", "bundle_id",
    "song_id", "title", "artists", "reaction", "comment",
]


def save_user_input(
    user_id: str,
    session_id: str,
    age: int,
    preferred_genres: list[str],
    preferred_artists: list[str],
    free_text: str = "",
) -> None:
    """온보딩 입력값을 UserInput 시트에 저장한다."""
    _ensure_header(USER_INPUT_SHEET, _USER_INPUT_HEADER)
    append_row(USER_INPUT_SHEET, [
        _now(), user_id, session_id, age,
        ",".join(preferred_genres),
        ",".join(preferred_artists),
        free_text,
    ])


def save_bundle(
    user_id: str,
    session_id: str,
    bundle: dict[str, Any],
) -> None:
    """추천 번들 결과를 Bundle 시트에 저장한다."""
    _ensure_header(BUNDLE_SHEET, _BUNDLE_HEADER)
    songs = bundle.get("songs", [])
    song_ids = ",".join(s["song_id"] for s in songs)
    append_row(BUNDLE_SHEET, [
        _now(),
        user_id,
        session_id,
        bundle.get("bundle_id", ""),
        bundle.get("emotion_title", ""),
        song_ids,
        bundle.get("next_action", ""),
    ])


def save_feedback(
    user_id: str,
    session_id: str,
    bundle_id: str,
    feedbacks: list[dict[str, Any]],
) -> None:
    """사용자 피드백을 Feedback 시트에 곡별로 한 행씩 저장한다."""
    _ensure_header(FEEDBACK_SHEET, _FEEDBACK_HEADER)
    ts = _now()
    for fb in feedbacks:
        append_row(FEEDBACK_SHEET, [
            ts,
            user_id,
            session_id,
            bundle_id,
            fb.get("song_id", ""),
            fb.get("title", ""),
            ",".join(fb.get("artists", [])),
            fb.get("reaction", ""),
            fb.get("comment", ""),
        ])


def load_song_catalog() -> list[dict[str, Any]]:
    """SongCatalog 시트에서 곡 목록을 읽어온다."""
    return read_all_records(SONG_CATALOG_SHEET)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_header(sheet_name: str, header: list[str]) -> None:
    from .sheets_client import get_sheet
    sheet = get_sheet(sheet_name)
    existing = sheet.row_values(1)
    if existing != header:
        sheet.insert_row(header, index=1)
