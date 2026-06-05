from __future__ import annotations

import os
from pathlib import Path

from .errors import MissingUpstageApiKeyError


def load_env_file(path: Path | str = Path("ai/.env")) -> None:
    path = Path(path)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_upstage_api_key(load_env: bool = True) -> str:
    if load_env:
        load_env_file()
    api_key = os.environ.get("UPSTAGE_API_KEY", "").strip()
    if not api_key:
        raise MissingUpstageApiKeyError("UPSTAGE_API_KEY is required. Put it in ai/.env or set it as an environment variable.")
    return api_key
