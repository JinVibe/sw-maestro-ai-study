from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    catalog_path: Path

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            catalog_path=Path(os.environ.get("CATALOG_PATH", "ai/data/raw/melon_kpop_2000_2025.jsonl")),
        )
