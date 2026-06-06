"""음악 추천 엔진 패키지입니다."""

from .selection import (
    CANDIDATE_SELECTION_TARGET_SIZE,
    FINAL_BUNDLE_SIZE,
    CandidateSelectionInput,
    CandidateSelectionOutput,
    PromptMessage,
    SelectionCandidate,
    SelectionContext,
    SelectionContextSongFeedback,
    SelectionSignals,
    build_candidate_selection_messages,
    build_candidate_selection_system_prompt,
    build_candidate_selection_user_prompt,
    candidate_selection_input_from_state,
    normalize_candidate_pool,
    parse_candidate_selection_output,
)
from .upstage_client import (
    UPSTAGE_DEFAULT_CHAT_MODEL,
    UpstageCandidateSelectorClient,
    UpstageEmbeddingClient,
    UpstageSelectionError,
)

__all__ = [
    "CANDIDATE_SELECTION_TARGET_SIZE",
    "FINAL_BUNDLE_SIZE",
    "CandidateSelectionInput",
    "CandidateSelectionOutput",
    "UPSTAGE_DEFAULT_CHAT_MODEL",
    "UpstageEmbeddingClient",
    "UpstageCandidateSelectorClient",
    "UpstageSelectionError",
    "PromptMessage",
    "SelectionCandidate",
    "SelectionContext",
    "SelectionContextSongFeedback",
    "SelectionSignals",
    "build_candidate_selection_messages",
    "build_candidate_selection_system_prompt",
    "build_candidate_selection_user_prompt",
    "candidate_selection_input_from_state",
    "normalize_candidate_pool",
    "parse_candidate_selection_output",
]
