from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---- 온보딩 ----
class CreateSessionRequest(BaseModel):
    age: int = Field(..., ge=1, le=120)
    preferred_genres: list[str] = Field(default_factory=list)
    preferred_artists: list[str] = Field(default_factory=list)
    user_id: str = ""


class SessionResponse(BaseModel):
    session_id: str
    user_id: str
    age: int
    preferred_genres: list[str]
    preferred_artists: list[str]
    next_action: str


# ---- 추천 ----
class RecommendRequest(BaseModel):
    session_id: str
    free_text: str = ""


class RecommendedSongOut(BaseModel):
    song_id: str
    title: str
    artists: list[str] = Field(default_factory=list)
    album: str = ""
    album_art_url: str = ""
    preview_url: str = ""
    slot_type: str = ""
    reason: str = ""


class BundleResponse(BaseModel):
    bundle_id: str
    emotion_title: str
    songs: list[RecommendedSongOut]
    next_action: str  # collect_feedback


# ---- 피드백 ----
class FeedbackItem(BaseModel):
    song_id: str
    title: str = ""
    artists: list[str] = Field(default_factory=list)
    reaction: Literal["좋아요", "싫어요"]
    saved: bool = False


class FeedbackRequest(BaseModel):
    session_id: str
    bundle_id: str = ""
    comment: str = ""  # 번들 전체에 대한 코멘트
    feedbacks: list[FeedbackItem]


class FeedbackResponse(BaseModel):
    negative_count: int
    # recommend_next_bundle / request_follow_up_text / finish
    next_action: str


# ---- 팔로업 텍스트 ----
class FollowUpRequest(BaseModel):
    text: str = Field(..., min_length=1)


class FollowUpResponse(BaseModel):
    next_action: str


# ---- 보관함 ----
class LibraryResponse(BaseModel):
    session_id: str
    songs: list[RecommendedSongOut]
