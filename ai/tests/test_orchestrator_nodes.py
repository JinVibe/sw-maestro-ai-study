from __future__ import annotations

import unittest

from ai.orchestrator.nodes import llm_select_20_candidates


class FakeSelector:
    def select_candidates_from_state(self, state: dict[str, object]) -> dict[str, object]:
        return {
            "selected_song_ids": ["song-1", "song-2"],
            "selection_reasons": {
                "song-1": "시대와 분위기가 잘 맞습니다.",
                "song-2": "선호 아티스트와 관련성이 높습니다.",
            },
        }


class OrchestratorNodeTest(unittest.TestCase):
    def test_llm_select_20_candidates_connects_selector_output_to_state(self) -> None:
        state = {
            "candidate_pool": [
                {"song_id": "song-1", "title": "첫 곡", "artists": ["아티스트 A"]},
                {"song_id": "song-2", "title": "둘째 곡", "artists": ["아티스트 B"]},
                {"song_id": "song-3", "title": "셋째 곡", "artists": ["아티스트 C"]},
            ]
        }

        result = llm_select_20_candidates(state, selector=FakeSelector())

        self.assertEqual([item["song_id"] for item in result["selected_candidates"]], ["song-1", "song-2"])
        self.assertEqual(result["selected_candidates"][0]["selection_reason"], "시대와 분위기가 잘 맞습니다.")
        self.assertEqual(result["selected_candidates"][0]["selection_order"], 1)
        self.assertEqual(result["selected_candidates"][1]["selection_reason"], "선호 아티스트와 관련성이 높습니다.")
        self.assertEqual(result["selected_candidates"][1]["selection_order"], 2)


if __name__ == "__main__":
    unittest.main()
