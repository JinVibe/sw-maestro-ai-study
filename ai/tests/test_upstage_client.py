from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ai.recommender.config import get_upstage_api_key, load_env_file
from ai.recommender.errors import MissingUpstageApiKeyError
from ai.recommender.upstage_client import (
    PASSAGE_MODEL,
    QUERY_MODEL,
    UpstageEmbeddingClient,
)


class FakeResponse:
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps({"data": [{"embedding": [0.1, 0.2]}]}).encode("utf-8")


class UpstageClientTest(unittest.TestCase):
    def test_load_env_file_sets_environment_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("UPSTAGE_API_KEY=test-key\nIGNORED_LINE\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {}, clear=True):
                load_env_file(path)

                self.assertEqual(os.environ["UPSTAGE_API_KEY"], "test-key")

    def test_missing_api_key_raises_clear_error(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(MissingUpstageApiKeyError):
                get_upstage_api_key(load_env=False)

    def test_embed_passages_uses_passage_model_payload(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["auth"] = request.headers["Authorization"]
            return FakeResponse()

        client = UpstageEmbeddingClient(api_key="key", urlopen_func=fake_urlopen)
        result = client.embed_passages(["hello"])

        self.assertEqual(result, [[0.1, 0.2]])
        self.assertEqual(captured["body"]["model"], PASSAGE_MODEL)
        self.assertEqual(captured["body"]["input"], ["hello"])
        self.assertEqual(captured["auth"], "Bearer key")

    def test_embed_query_uses_query_model_payload(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse()

        client = UpstageEmbeddingClient(api_key="key", urlopen_func=fake_urlopen)
        client.embed_query("hello")

        self.assertEqual(captured["body"]["model"], QUERY_MODEL)
        self.assertEqual(captured["body"]["input"], ["hello"])


if __name__ == "__main__":
    unittest.main()
