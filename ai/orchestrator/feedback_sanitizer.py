from __future__ import annotations

from typing import Any

from ..recommender.models import Feedback
from .state import RecommendationContext, RecommendationSessionState


def extract_feedback_songs(state: RecommendationSessionState) -> list[dict[str, Any]]:
    context = state.get("context") or {}
    if isinstance(context, dict):
        songs = context.get("songs", [])
        if isinstance(songs, list) and songs:
            return _deduplicate_feedback_songs([song for song in songs if isinstance(song, dict)])

    final_bundle = state.get("final_bundle", [])
    if isinstance(final_bundle, list) and final_bundle:
        return _deduplicate_feedback_songs([song for song in final_bundle if isinstance(song, dict)])

    return []


def feedback_from_song(song: dict[str, Any]) -> Feedback:
    return Feedback(
        song_id=str(song.get("song_id") or "").strip(),
        reaction=_normalize_reaction(str(song.get("reaction") or "")),
        saved=bool(song.get("saved", False)),
    )


def merge_exclude_song_ids(existing_ids: list[str], new_ids: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for song_id in [*existing_ids, *new_ids]:
        normalized = str(song_id).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        merged.append(normalized)
    return merged


def sanitize_context(context: dict[str, Any] | None) -> RecommendationContext:
    if not isinstance(context, dict):
        return {"bundle_id": "", "songs": [], "feedback_summary": {}}
    bundle_id = str(context.get("bundle_id") or "").strip()
    songs = context.get("songs", [])
    if not isinstance(songs, list):
        songs = []
    sanitized_songs = []
    for song in songs:
        if not isinstance(song, dict):
            continue
        reaction = _normalize_reaction(str(song.get("reaction") or ""))
        if not reaction:
            continue
        sanitized_songs.append(
            {
                "song_id": str(song.get("song_id") or "").strip(),
                "title": str(song.get("title") or "").strip(),
                "artists": [str(artist).strip() for artist in song.get("artists", []) if str(artist).strip()],
                "reaction": reaction,
            }
        )
    raw_summary = context.get("feedback_summary")
    feedback_summary: dict[str, Any] = {}
    if isinstance(raw_summary, dict):
        raw_comment = _normalize_comment(str(raw_summary.get("comment") or ""))
        if raw_comment:
            feedback_summary["comment"] = raw_comment
    return {"bundle_id": bundle_id, "songs": sanitized_songs, "feedback_summary": feedback_summary}


def _deduplicate_feedback_songs(songs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for song in songs:
        song_id = str(song.get("song_id") or "").strip()
        if not song_id or song_id in seen:
            continue
        seen.add(song_id)
        unique.append(song)
    return unique


def _normalize_reaction(value: str) -> str:
    normalized = " ".join(value.strip().split())
    if normalized in {"좋아요", "싫어요"}:
        return normalized
    return ""


def _normalize_comment(value: str) -> str:
    normalized = " ".join(value.strip().split())
    if len(normalized) < 2:
        return ""
    if len(set(normalized)) <= 1:
        return ""
    if all(not ch.isalnum() and not ("\uac00" <= ch <= "\ud7a3") for ch in normalized):
        return ""
    return normalized

