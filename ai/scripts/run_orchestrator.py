"""
오케스트레이터 실행 스크립트.

흐름:
    1. 온보딩 JSON 입력 (형식 1) → Recommender 요청 JSON 출력
    2. 번들 JSON 입력 (형식 2) → Recommender 요청 JSON 출력
    3. q 입력 시 종료

실행:
    python -m ai.scripts.run_orchestrator
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.orchestrator.orchestrator import Orchestrator


def read_json_from_first_line(first_line: str) -> dict:
    lines = [first_line]
    depth = first_line.count("{") + first_line.count("[") - first_line.count("}") - first_line.count("]")
    started = first_line.strip().startswith("{")
    while not (started and depth == 0):
        line = input()
        lines.append(line)
        depth += line.count("{") + line.count("[")
        depth -= line.count("}") + line.count("]")
        if line.strip().startswith("{"):
            started = True
    return json.loads("\n".join(lines))


def print_output(result: dict) -> None:
    print("\n" + "=" * 50)
    print("  출력 JSON")
    print("=" * 50)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    print("=" * 50)
    print("  Orchestrator 실행")
    print("=" * 50)

    orch = Orchestrator()

    while True:
        print("\nJSON을 붙여넣거나 q로 종료하세요:")
        first_line = input().strip()

        if first_line.lower() == "q":
            break

        try:
            payload = read_json_from_first_line(first_line)
            result = orch.process(payload)
            print_output(result)
        except Exception as e:
            print(f"오류: {e}")


if __name__ == "__main__":
    main()
