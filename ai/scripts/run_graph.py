"""
오케스트레이터 그래프 테스트 스크립트.

입력 형식 1 — 온보딩 (첫 추천):
    {
      "user_id": "user_1",
      "session_id": "sess_1",
      "age": 25,
      "preferred_genres": ["발라드"],
      "preferred_artists": ["아이유"],
      "free_text": "밤에 듣기 좋은 노래"
    }

입력 형식 2 — 피드백 (다음 추천):
    {
      "bundle_id": "...",
      "songs": [
        {"song_id": "...", "reaction": "좋아요"},
        {"song_id": "...", "reaction": "싫어요"}
      ]
    }

실행:
    python -m ai.scripts.run_graph
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.orchestrator import build_recommendation_graph, resume_with_feedback, start_recommendation

CATALOG_PATH = "ai/data/raw/melon_kpop_2000_2025.jsonl"


def read_json() -> dict:
    print("JSON을 붙여넣고 엔터 두 번 (또는 q로 종료):")
    lines = []
    while True:
        line = input()
        if line.strip().lower() == "q":
            raise SystemExit(0)
        lines.append(line)
        text = "\n".join(lines).strip()
        if not text:
            continue
        depth = text.count("{") + text.count("[") - text.count("}") - text.count("]")
        if depth == 0 and text.startswith("{"):
            return json.loads(text)


def print_output(data: dict | list) -> None:
    print("\n" + "=" * 50)
    print("  출력 JSON")
    print("=" * 50)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print("=" * 50)


def main() -> None:
    print("=" * 50)
    print("  Orchestrator 그래프 테스트")
    print("=" * 50)

    graph = build_recommendation_graph()
    session_id: str | None = None

    while True:
        print()
        try:
            payload = read_json()
        except (EOFError, KeyboardInterrupt):
            break

        try:
            if "user_id" in payload:
                session_id = payload.get("session_id", "default")
                payload.setdefault("catalog_path", CATALOG_PATH)
                songs = start_recommendation(payload, thread_id=session_id, graph=graph)
                print_output({"final_bundle": songs})

            elif "bundle_id" in payload:
                if not session_id:
                    print("오류: 온보딩 JSON을 먼저 입력하세요.")
                    continue
                result = resume_with_feedback(payload, thread_id=session_id, graph=graph)
                print_output(result)

            else:
                print("오류: user_id 또는 bundle_id 필드가 필요합니다.")

        except Exception as e:
            print(f"오류: {e}")


if __name__ == "__main__":
    main()
