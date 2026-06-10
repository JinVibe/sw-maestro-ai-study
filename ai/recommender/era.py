from __future__ import annotations

from datetime import date
import re

from .models import Song


DATASET_START_YEAR = 2000
DATASET_END_YEAR = 2025


def default_preferred_year_center(
    dataset_start_year: int = DATASET_START_YEAR,
    dataset_end_year: int = DATASET_END_YEAR,
) -> float:
    return (dataset_start_year + dataset_end_year) / 2


def preferred_year_center_from_age(
    age: int,
    current_year: int | None = None,
    dataset_start_year: int = DATASET_START_YEAR,
    dataset_end_year: int = DATASET_END_YEAR,
) -> float:
    if current_year is None:
        current_year = date.today().year
    birth_year = current_year - age
    target_year = birth_year + 18
    return max(dataset_start_year, min(dataset_end_year, target_year))


def release_year(song: Song) -> int | None:
    if song.release_date:
        match = re.search(r"\d{4}", song.release_date)
        if match:
            return int(match.group(0))
    years = [
        int(appearance["year"])
        for appearance in song.chart_appearances
        if isinstance(appearance, dict) and str(appearance.get("year", "")).isdigit()
    ]
    return min(years) if years else None


def era_score(release_year_value: int | None, preferred_year_center: float, era_window: float = 12.5) -> float:
    if release_year_value is None:
        return 0.0
    distance = abs(release_year_value - preferred_year_center)
    if distance <= 0.5:
        return 1.0
    return max(0.0, min(1.0, 1.0 - distance / era_window))


def shift_preferred_year_center(
    preferred_year_center: float,
    era_shift: float = 0.0,
    dataset_start_year: int = DATASET_START_YEAR,
    dataset_end_year: int = DATASET_END_YEAR,
) -> float:
    shifted = preferred_year_center + era_shift
    return max(dataset_start_year, min(dataset_end_year, shifted))
