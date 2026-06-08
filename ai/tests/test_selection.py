from __future__ import annotations

import unittest

from ai.recommender.selection import (
    CANDIDATE_SELECTION_TARGET_SIZE,
    FINAL_BUNDLE_SIZE,
    build_candidate_selection_messages,
    build_candidate_selection_system_prompt,
    build_candidate_selection_user_prompt,
    candidate_selection_input_from_state,
)


class SelectionPromptTest(unittest.TestCase):
    def test_system_prompt_mentions_selection_rules(self) -> None:
        prompt = build_candidate_selection_system_prompt()

        self.assertIn(str(CANDIDATE_SELECTION_TARGET_SIZE), prompt)
        self.assertIn(str(FINAL_BUNDLE_SIZE), prompt)
        self.assertIn("나이 기반 시대 근접성", prompt)
        self.assertIn("선호 장르 일치", prompt)
        self.assertIn("선호 아티스트 일치", prompt)

    def test_user_prompt_serializes_state_payload(self) -> None:
        prompt = build_candidate_selection_user_prompt(
            {
                "user_id": "user_123",
                "session_id": "sess_abc",
                "age": 36,
                "preferred_genres": ["발라드"],
                "preferred_artists": ["조성모"],
                "free_text": "밤에 산책할 때 듣고 싶어요",
                "context_text": "싫어요 3곡",
                "exclude_song_ids": ["1", "2"],
                "negative_count": 3,
                "candidate_pool": [
                    {
                        "song_id": "3849494",
                        "title": "이등병의 편지",
                        "artists": ["김광석"],
                        "match_signals": {"era": 1.0, "text": 0.8},
                    }
                ],
            }
        )

        self.assertIn('"user_123"', prompt)
        self.assertIn('"session_id": "sess_abc"', prompt)
        self.assertIn('"negative_count": 3', prompt)
        self.assertIn('"song_id": "3849494"', prompt)

    def test_state_input_uses_age_when_year_center_is_missing(self) -> None:
        payload = candidate_selection_input_from_state(
            {
                "user_id": "user_123",
                "session_id": "sess_abc",
                "age": 36,
                "preferred_genres": ["발라드"],
                "preferred_artists": ["조성모"],
                "free_text": "밤에 산책할 때 듣고 싶어요",
                "context_text": "싫어요 3곡",
                "exclude_song_ids": ["1", "2"],
                "negative_count": 3,
                "candidate_pool": [],
            }
        )

        self.assertEqual(payload["age"], 36)
        self.assertIsNotNone(payload["preferred_year_center"])
        self.assertEqual(payload["target_size"], CANDIDATE_SELECTION_TARGET_SIZE)
        self.assertEqual(payload["final_size"], FINAL_BUNDLE_SIZE)

    def test_messages_use_system_and_user_roles(self) -> None:
        messages = build_candidate_selection_messages(
            {
                "user_id": "user_123",
                "session_id": "sess_abc",
                "age": 36,
                "preferred_genres": ["발라드"],
                "preferred_artists": ["조성모"],
                "free_text": "밤에 산책할 때 듣고 싶어요",
                "candidate_pool": [],
            }
        )

        self.assertEqual([message["role"] for message in messages], ["system", "user"])


if __name__ == "__main__":
    unittest.main()
