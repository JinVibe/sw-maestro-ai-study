from __future__ import annotations

import json
from typing import Any, Callable, Literal, TypedDict
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .config import get_upstage_api_key
from .errors import RecommenderError
from .selection import (
    CandidateSelectionInput,
    CandidateSelectionOutput,
    build_candidate_selection_messages,
    candidate_selection_input_from_state,
    normalize_candidate_pool,
    parse_candidate_selection_output,
)
from .preference_expansion import (
    PreferenceExpansionInput,
    PreferenceExpansionOutput,
    build_preference_expansion_messages,
    parse_preference_expansion_output,
)


UPSTAGE_EMBEDDING_URL = "https://api.upstage.ai/v1/solar/embeddings"
UPSTAGE_CHAT_COMPLETIONS_URL = "https://api.upstage.ai/v1/chat/completions"
PASSAGE_MODEL = "solar-embedding-1-large-passage"
QUERY_MODEL = "solar-embedding-1-large-query"
UPSTAGE_DEFAULT_CHAT_MODEL = "solar-pro3"


class UpstageSelectionError(RecommenderError):
    """Upstage 후보 선택 요청이 실패했을 때 발생합니다."""


class UpstageEmbeddingClient:
    def __init__(
        self,
        api_key: str | None = None,
        embedding_url: str = UPSTAGE_EMBEDDING_URL,
        timeout: float = 30.0,
        urlopen_func: Callable[..., object] = urlopen,
    ) -> None:
        self.api_key = api_key or get_upstage_api_key()
        self.embedding_url = embedding_url
        self.timeout = timeout
        self.urlopen_func = urlopen_func

    def embed_texts(self, texts: list[str], model: str) -> list[list[float]]:
        payload = json.dumps({"model": model, "input": texts}, ensure_ascii=False).encode("utf-8")
        request = Request(
            self.embedding_url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with self.urlopen_func(request, timeout=self.timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        return [item["embedding"] for item in body.get("data", [])]

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return self.embed_texts(texts, PASSAGE_MODEL)

    def embed_query(self, text: str) -> list[float]:
        embeddings = self.embed_texts([text], QUERY_MODEL)
        return embeddings[0] if embeddings else []


class UpstagePreferenceExpansionError(RecommenderError):
    """Upstage 선호도 확장 요청이 실패했을 때 발생합니다."""


class UpstagePreferenceExpanderClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = UPSTAGE_DEFAULT_CHAT_MODEL,
        timeout: float = 30.0,
        urlopen_func: Callable[..., object] = urlopen,
    ) -> None:
        self.api_key = api_key or get_upstage_api_key()
        self.model = model
        self.timeout = timeout
        self.urlopen_func = urlopen_func

    def expand_preferences(self, payload: PreferenceExpansionInput) -> PreferenceExpansionOutput:
        messages = build_preference_expansion_messages(payload)
        body = {
            "model": self.model,
            "messages": [
                {"role": message["role"], "content": message["content"]}
                for message in messages
            ],
            "temperature": 0.2,
            "top_p": 0.8,
            "max_tokens": 2048,
            "response_format": {"type": "json_object"},
        }
        request = Request(
            UPSTAGE_CHAT_COMPLETIONS_URL,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self.urlopen_func(request, timeout=self.timeout) as response:
                response_body = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise UpstagePreferenceExpansionError(f"Upstage API 요청이 실패했습니다: {error.code}") from error
        except Exception as error:  # pragma: no cover - 네트워크/예상치 못한 예외 안전망
            raise UpstagePreferenceExpansionError(f"Upstage API 요청 중 알 수 없는 오류가 발생했습니다: {error}") from error

        choices = response_body.get("choices", [])
        if not choices:
            raise UpstagePreferenceExpansionError("Upstage 응답에서 확장 결과가 없습니다.")
        message = choices[0].get("message", {})
        text = message.get("content", "")
        if isinstance(text, list):
            text = "".join(part.get("text", "") for part in text if isinstance(part, dict))
        if not isinstance(text, str) or not text.strip():
            raise UpstagePreferenceExpansionError("Upstage 응답에서 텍스트를 찾지 못했습니다.")
        return parse_preference_expansion_output(text)


class UpstageCandidateSelectorClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = UPSTAGE_DEFAULT_CHAT_MODEL,
        timeout: float = 30.0,
        urlopen_func: Callable[..., object] = urlopen,
    ) -> None:
        self.api_key = api_key or get_upstage_api_key()
        self.model = model
        self.timeout = timeout
        self.urlopen_func = urlopen_func

    def select_candidates(self, payload: CandidateSelectionInput) -> CandidateSelectionOutput:
        normalized_pool = normalize_candidate_pool(payload.get("candidate_pool", []))
        payload = dict(payload)
        payload["candidate_pool"] = normalized_pool
        messages = build_candidate_selection_messages(payload)
        body = {
            "model": self.model,
            "messages": [
                {"role": message["role"], "content": message["content"]}
                for message in messages
            ],
            "temperature": 0.2,
            "top_p": 0.8,
            "max_tokens": 8192,
            "response_format": {"type": "json_object"},
        }
        request = Request(
            UPSTAGE_CHAT_COMPLETIONS_URL,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self.urlopen_func(request, timeout=self.timeout) as response:
                response_body = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise UpstageSelectionError(f"Upstage API 요청에 실패했습니다: {error.code}") from error
        except Exception as error:  # pragma: no cover - 네트워크/런타임 예외 안전망
            raise UpstageSelectionError(f"Upstage API 요청 중 알 수 없는 오류가 발생했습니다: {error}") from error

        choices = response_body.get("choices", [])
        if not choices:
            raise UpstageSelectionError("Upstage 응답에 선택 결과가 없습니다.")
        message = choices[0].get("message", {})
        text = message.get("content", "")
        if isinstance(text, list):
            text = "".join(part.get("text", "") for part in text if isinstance(part, dict))
        if not isinstance(text, str) or not text.strip():
            raise UpstageSelectionError("Upstage 응답에서 텍스트를 찾지 못했습니다.")
        print(f"[Recommender] LLM 응답 원문 (앞 500자): {text[:500]}")
        output = parse_candidate_selection_output(text)
        self._validate_output(output, normalized_pool, payload.get("target_size", 20))
        return output

    @staticmethod
    def _validate_output(
        output: CandidateSelectionOutput,
        candidate_pool: list[dict[str, Any]],
        target_size: int,
    ) -> None:
        candidate_ids = {candidate.get("song_id", "") for candidate in candidate_pool}
        selected_song_ids = output["selected_song_ids"]
        if len(selected_song_ids) > target_size:
            raise UpstageSelectionError("Upstage가 허용된 후보 수보다 많은 곡을 선택했습니다.")
        if len(set(selected_song_ids)) != len(selected_song_ids):
            raise UpstageSelectionError("Upstage 응답에 중복 song_id가 있습니다.")
        if not set(selected_song_ids).issubset(candidate_ids):
            raise UpstageSelectionError("Upstage가 후보 풀에 없는 곡을 선택했습니다.")

    def select_candidates_from_state(self, state: dict[str, Any]) -> CandidateSelectionOutput:
        return self.select_candidates(candidate_selection_input_from_state(state))
