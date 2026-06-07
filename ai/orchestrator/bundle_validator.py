from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

BUNDLE_SIZE = 5
_VARIANT_PATTERN = re.compile(
    r"\b(live|remaster(ed)?|instrumental|remix|acoustic|karaoke|inst\.?)\b",
    re.IGNORECASE,
)


@dataclass
class ValidationResult:
    ok: bool
    reasons: list[str]


def validate_bundle(bundle: dict[str, Any], session_id: str) -> ValidationResult:
    reasons: list[str] = []
    songs: list[dict[str, Any]] = bundle.get("songs", [])

    if len(songs) != BUNDLE_SIZE:
        reasons.append(f"곡 수 오류: {len(songs)}곡 (기대값 {BUNDLE_SIZE}곡)")

    song_ids = [s.get("song_id") for s in songs]
    if len(song_ids) != len(set(song_ids)):
        reasons.append("중복 곡 포함")

    for song in songs:
        if not song.get("preview_url"):
            reasons.append(f"preview_url 없음: {song.get('title', song.get('song_id'))}")
        title = song.get("title", "")
        if _VARIANT_PATTERN.search(title):
            reasons.append(f"변형 버전 포함: {title}")

    return ValidationResult(ok=len(reasons) == 0, reasons=reasons)
