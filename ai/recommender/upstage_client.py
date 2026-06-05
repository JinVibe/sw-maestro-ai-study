from __future__ import annotations

import json
from typing import Callable
from urllib.request import Request, urlopen

from .config import get_upstage_api_key


UPSTAGE_EMBEDDING_URL = "https://api.upstage.ai/v1/solar/embeddings"
PASSAGE_MODEL = "solar-embedding-1-large-passage"
QUERY_MODEL = "solar-embedding-1-large-query"


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
