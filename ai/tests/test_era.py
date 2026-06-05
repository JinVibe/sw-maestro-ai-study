from __future__ import annotations

import unittest

from ai.recommender.era import (
    default_preferred_year_center,
    era_score,
    preferred_year_center_from_age,
    release_year,
    shift_preferred_year_center,
)
from ai.recommender.models import Song


class EraTest(unittest.TestCase):
    def test_default_preferred_year_center_is_dataset_midpoint(self) -> None:
        self.assertEqual(default_preferred_year_center(2000, 2025), 2012.5)

    def test_preferred_year_center_from_age_converts_midpoint_age_back_to_year(self) -> None:
        self.assertEqual(preferred_year_center_from_age(26, current_year=2026, dataset_start_year=2000, dataset_end_year=2025), 2012.5)
        self.assertEqual(preferred_year_center_from_age(36, current_year=2026, dataset_start_year=2000, dataset_end_year=2025), 2012.5)

    def test_release_year_prefers_release_date(self) -> None:
        song = Song(song_id="1", title="A", release_date="2000.09.01", chart_appearances=[{"year": 2001}])

        self.assertEqual(release_year(song), 2000)

    def test_release_year_falls_back_to_chart_year(self) -> None:
        song = Song(song_id="1", title="A", chart_appearances=[{"year": 2001, "rank": 1}])

        self.assertEqual(release_year(song), 2001)

    def test_era_score_is_highest_near_preferred_year_center(self) -> None:
        center = 2012.5

        self.assertEqual(era_score(2012, center), 1.0)
        self.assertGreater(era_score(2006, center), era_score(2000, center))

    def test_shift_preferred_year_center_applies_agent_numeric_shift_with_clamp(self) -> None:
        self.assertEqual(shift_preferred_year_center(2012.5, -4), 2008.5)
        self.assertEqual(shift_preferred_year_center(2012.5, 4), 2016.5)
        self.assertEqual(shift_preferred_year_center(2012.5, 0), 2012.5)
        self.assertEqual(shift_preferred_year_center(2001, -4), 2000)
        self.assertEqual(shift_preferred_year_center(2024, 4), 2025)


if __name__ == "__main__":
    unittest.main()
