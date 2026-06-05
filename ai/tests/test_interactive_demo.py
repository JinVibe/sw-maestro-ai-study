from __future__ import annotations

import unittest

from ai.scripts.recommend_interactive import split_user_values


class InteractiveDemoTest(unittest.TestCase):
    def test_split_user_values_accepts_commas_and_spaces(self) -> None:
        self.assertEqual(split_user_values("발라드, 댄스 R&B"), ["발라드", "댄스", "R&B"])

    def test_split_user_values_returns_empty_list_for_blank_input(self) -> None:
        self.assertEqual(split_user_values("   "), [])


if __name__ == "__main__":
    unittest.main()
