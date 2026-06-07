from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


DEFAULT_STRATEGY_WEIGHTS = {
    "w_theme": 0.50,
    "w_era": 0.20,
    "w_discovery": 0.20,
    "w_quality": 0.10,
}


@dataclass
class SongFeedback:
    song_id: str
    title: str
    artists: list[str]
    reaction: str  # "좋아요" | "싫어요"
    comment: str = ""


@dataclass
class BundleHistory:
    bundle_id: str
    songs: list[SongFeedback] = field(default_factory=list)


@dataclass
class SessionContext:
    user_id: str
    session_id: str
    age: int
    preferred_genres: list[str]
    preferred_artists: list[str]
    free_text: str = ""

    strategy_weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_STRATEGY_WEIGHTS))
    preferred_year_center: float | None = None
    exclude_song_ids: list[str] = field(default_factory=list)
    negative_count: int = 0
    follow_up_text: str = ""
    bundle_history: list[BundleHistory] = field(default_factory=list)

    def last_bundle(self) -> BundleHistory | None:
        return self.bundle_history[-1] if self.bundle_history else None

    def add_bundle(self, bundle_id: str) -> BundleHistory:
        bundle = BundleHistory(bundle_id=bundle_id)
        self.bundle_history.append(bundle)
        return bundle

    def apply_feedback(self, feedbacks: list[SongFeedback]) -> None:
        """피드백을 현재 번들에 기록하고 세션 상태를 업데이트한다."""
        bundle = self.last_bundle()
        if bundle:
            bundle.songs = feedbacks

        for fb in feedbacks:
            if fb.song_id not in self.exclude_song_ids:
                self.exclude_song_ids.append(fb.song_id)
            if fb.reaction == "싫어요":
                self.negative_count += 1
            if fb.comment:
                self.follow_up_text = fb.comment

    def to_context_dict(self) -> dict[str, Any]:
        bundle = self.last_bundle()
        if not bundle:
            return {"bundle_id": "", "songs": [], "feedback_summary": {}}
        return {
            "bundle_id": bundle.bundle_id,
            "songs": [
                {
                    "song_id": fb.song_id,
                    "title": fb.title,
                    "artists": fb.artists,
                    "reaction": fb.reaction,
                }
                for fb in bundle.songs
            ],
        }

    def to_recommender_request(self, catalog_path: str = "ai/data/samples/melon_kpop_sample.jsonl") -> dict[str, Any]:
        context = self.to_context_dict()
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "age": self.age,
            "preferred_genres": self.preferred_genres,
            "preferred_artists": self.preferred_artists,
            "free_text": self.free_text,
            "context": context,
            "context_text": json.dumps(context, ensure_ascii=False) if context["bundle_id"] else "",
            "follow_up_text": self.follow_up_text,
            "exclude_song_ids": self.exclude_song_ids,
            "catalog_path": catalog_path,
            "candidate_source": [],
            "expanded_preferred_genres": [],
            "expanded_preferred_artists": [],
            "preference_expansion": {},
            "negative_count": self.negative_count,
            "next_action": "recommend_next_bundle",
        }
