from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Artist:
    artist_id: str = ""
    name: str = ""


@dataclass(frozen=True)
class Album:
    album_id: str | None = None
    name: str = ""


@dataclass(frozen=True)
class Song:
    song_id: str
    title: str
    artists: list[Artist] = field(default_factory=list)
    album: Album = field(default_factory=Album)
    release_date: str | None = None
    genres: list[str] = field(default_factory=list)
    flac: str | None = None
    like_count: int = 0
    lyrics: str = ""
    chart_appearances: list[dict[str, Any]] = field(default_factory=list)
    source_urls: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RecommendationOptions:
    bundle_size: int = 5

    def __post_init__(self) -> None:
        if not 5 <= self.bundle_size <= 7:
            raise ValueError("bundle_size must be between 5 and 7")


@dataclass(frozen=True)
class RecommendationRequest:
    user_id: str = ""
    session_id: str = ""
    age: int | None = None
    preferred_year_center: float | None = None
    preferred_genres: list[str] = field(default_factory=list)
    preferred_artists: list[str] = field(default_factory=list)
    free_text: str = ""
    # 오케스트레이터가 넘겨주는 context text입니다. 앞으로 프롬프트 기반 랭킹에 사용합니다.
    context_text: str = ""
    exclude_song_ids: list[str] = field(default_factory=list)
    options: RecommendationOptions | dict[str, Any] = field(default_factory=RecommendationOptions)

    def __post_init__(self) -> None:
        if isinstance(self.options, dict):
            object.__setattr__(self, "options", RecommendationOptions(**self.options))


@dataclass(frozen=True)
class ScoreBreakdown:
    theme: float
    era: float
    discovery: float
    quality: float
    penalties: float
    final: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class RecommendedSong:
    song_id: str
    title: str
    artists: list[str]
    album: str = ""
    album_art_url: str = ""
    preview_url: str = ""
    slot_type: str = "theme_match"
    reason: str = ""
    score_breakdown: ScoreBreakdown | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.score_breakdown is not None:
            data["score_breakdown"] = self.score_breakdown.to_dict()
        return data


@dataclass(frozen=True)
class RecommendationBundle:
    bundle_id: str
    emotion_title: str
    songs: list[RecommendedSong]
    next_action: str = "collect_feedback"

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "emotion_title": self.emotion_title,
            "songs": [song.to_dict() for song in self.songs],
            "next_action": self.next_action,
        }


@dataclass(frozen=True)
class Feedback:
    song_id: str
    reaction: str
    saved: bool = False
