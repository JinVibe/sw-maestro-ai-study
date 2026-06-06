from __future__ import annotations

import unittest

from ai.orchestrator.nodes import collect_feedback, decide_next_action, route_after_feedback


class FeedbackLoopNodeTest(unittest.TestCase):
    def test_collect_feedback_counts_negative_reactions_and_merges_excludes(self) -> None:
        state = {
            "exclude_song_ids": ["1"],
            "context": {
                "bundle_id": "bundle_001",
                "songs": [
                    {"song_id": "1", "title": "A", "artists": ["Artist A"], "reaction": "좋아요"},
                    {"song_id": "2", "title": "B", "artists": ["Artist B"], "reaction": "싫어요"},
                    {"song_id": "3", "title": "C", "artists": ["Artist C"], "reaction": "싫어요"},
                    {"song_id": "4", "title": "D", "artists": ["Artist D"], "reaction": "좋아요"},
                    {"song_id": "5", "title": "E", "artists": ["Artist E"], "reaction": "싫어요"},
                ],
            },
        }

        result = collect_feedback(state)

        self.assertEqual(result["negative_count"], 3)
        self.assertEqual(result["exclude_song_ids"], ["1", "2", "3", "4", "5"])

    def test_decide_next_action_requests_follow_up_when_three_dislikes_without_text(self) -> None:
        state = {"negative_count": 3, "follow_up_text": ""}

        result = decide_next_action(state)

        self.assertEqual(result["next_action"], "request_follow_up_text")

    def test_decide_next_action_recommends_next_bundle_after_follow_up_text(self) -> None:
        state = {"negative_count": 3, "follow_up_text": "좀 더 옛날 노래로 해줘"}

        result = decide_next_action(state)

        self.assertEqual(result["next_action"], "recommend_next_bundle")
        self.assertEqual(route_after_feedback({"next_action": result["next_action"]}), "recommend_next_bundle")


if __name__ == "__main__":
    unittest.main()
