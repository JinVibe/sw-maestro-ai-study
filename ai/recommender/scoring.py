from __future__ import annotations

import math

from .era import era_score, preferred_year_center_from_age, release_year
from .models import RecommendationRequest, ScoreBreakdown, Song


DEFAULT_WEIGHTS = {"w_theme": 0.50, "w_era": 0.20, "w_discovery": 0.20, "w_quality": 0.10}
WEIGHT_KEYS = set(DEFAULT_WEIGHTS)


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(left * right for left, right in zip(a, b))
    norm_a = math.sqrt(sum(value * value for value in a))
    norm_b = math.sqrt(sum(value * value for value in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def calculate_quality_score(song: Song) -> float:
    like_score = min(math.log1p(max(song.like_count, 0)) / 12.0, 0.4)
    # 곡 최고 순위(연도와 무관)
    best_rank = min((appearance.get("rank", 101) for appearance in song.chart_appearances), default=101)
    # 최고 순위 기준 점수
    chart_score = 0.35 if best_rank <= 10 else 0.25 if best_rank <= 50 else 0.15 if best_rank <= 100 else 0.0
    # 메타데이터 완성도
    completeness = sum(
        [
            bool(song.title),
            bool(song.artists),
            bool(song.album.name),
            bool(song.genres),
            bool(song.lyrics),
        ]
    ) / 5.0 * 0.25
    return clamp(like_score + chart_score + completeness)


def calculate_discovery_score(song: Song, request: RecommendationRequest) -> float:
    familiarity = 0.0
    best_rank = min((appearance.get("rank", 101) for appearance in song.chart_appearances), default=101)
    if best_rank <= 20:
        familiarity += 0.35
    elif best_rank <= 100:
        familiarity += 0.2
    return clamp(1.0 - familiarity)


def calculate_era_score(song: Song, request: RecommendationRequest) -> float:
    center = request.preferred_year_center
    if center is None:
        if request.age is None:
            return 0.0
        center = preferred_year_center_from_age(request.age)
    return era_score(release_year(song), center)


def calculate_penalties(song: Song, selected: list[Song], exclude_song_ids: list[str]) -> float:
    penalty = 0.0
    if song.song_id in set(exclude_song_ids):
        penalty += 1.0
    selected_artists = {artist.name for item in selected for artist in item.artists if artist.name}
    if any(artist.name in selected_artists for artist in song.artists):
        penalty += 0.2
    return penalty


def normalize_strategy_weights(weights: dict[str, float] | None) -> dict[str, float]:
    if weights is None:
        weights = DEFAULT_WEIGHTS
    if set(weights) != WEIGHT_KEYS:
        raise ValueError(f"strategy_weights must contain exactly {sorted(WEIGHT_KEYS)}")
    normalized_input = {key: float(value) for key, value in weights.items()}
    if any(value < 0 for value in normalized_input.values()):
        raise ValueError("strategy_weights values must be non-negative")
    total = sum(normalized_input.values())
    if total <= 0:
        raise ValueError("strategy_weights sum must be greater than 0")
    return {key: value / total for key, value in normalized_input.items()}


def calculate_final_score(
    song: Song,
    request: RecommendationRequest,
    theme_similarity: float,
    selected: list[Song],
    exclude_song_ids: list[str],
    weights: dict[str, float] | None = None,
) -> ScoreBreakdown:
    weights = normalize_strategy_weights(weights)
    theme = clamp((theme_similarity + 1.0) / 2.0)
    era = calculate_era_score(song, request)
    discovery = calculate_discovery_score(song, request)
    quality = calculate_quality_score(song)
    penalties = calculate_penalties(song, selected, exclude_song_ids)
    final = (
        weights["w_theme"] * theme
        + weights["w_era"] * era
        + weights["w_discovery"] * discovery
        + weights["w_quality"] * quality
        - penalties
    )
    return ScoreBreakdown(theme, era, discovery, quality, penalties, final)
