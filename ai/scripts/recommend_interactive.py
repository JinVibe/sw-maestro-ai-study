from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.recommender.catalog import load_songs
from ai.recommender.embedding_store import DEFAULT_EMBEDDING_CACHE_PATH, load_embedding_cache
from ai.recommender.engine import RecommendationEngine
from ai.recommender.era import default_preferred_year_center
from ai.recommender.errors import MissingEmbeddingCacheError, RecommendationInputError
from ai.recommender.models import RecommendationRequest
from ai.recommender.upstage_client import UpstageEmbeddingClient


#DEFAULT_CATALOG_PATH = Path("ai/data/samples/melon_kpop_sample.jsonl")
DEFAULT_CATALOG_PATH = Path("ai/data/raw/melon_kpop_2000_2025.jsonl")

def split_user_values(value: str) -> list[str]:
    normalized = value.replace(",", " ")
    return [item.strip() for item in normalized.split() if item.strip()]


def prompt_required(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("free text는 필수입니다. 예: 밤에 산책할 때 듣고 싶어요")


def prompt_age(prompt: str) -> int:
    while True:
        value = input(prompt).strip()
        if value.isdigit() and int(value) > 0:
            return int(value)
        print("나이는 양의 정수로 입력해주세요. 예: 36")


def print_bundle(bundle) -> None:
    print("\n=== 추천 결과 ===")
    print(f"묶음 ID: {bundle.bundle_id}")
    print(f"감성 타이틀: {bundle.emotion_title}")
    print(f"다음 액션: {bundle.next_action}")
    for index, song in enumerate(bundle.songs, start=1):
        scores = song.score_breakdown
        print(f"\n{index}. {song.title} - {', '.join(song.artists)}")
        print(f"   slot: {song.slot_type}")
        print(f"   reason: {song.reason}")
        if scores:
            print(
                "   scores: "
                f"final={scores.final:.4f}, "
                f"theme={scores.theme:.4f}, "
                f"preference={scores.preference:.4f}, "
                f"era={scores.era:.4f}, "
                f"discovery={scores.discovery:.4f}, "
                f"quality={scores.quality:.4f}, "
                f"penalties={scores.penalties:.4f}"
            )


def run_interactive(
    catalog_path: Path,
    embeddings_path: Path,
    bundle_size: int,
    free_text_arg: str = "",
    age_arg: int | None = None,
    preferred_year_center_arg: float | None = None,
    genres_arg: list[str] | None = None,
    artists_arg: list[str] | None = None,
) -> int:
    print("=== AI 음악 추천 v1 데모 ===")
    print("가사 임베딩과 free text 임베딩의 cosine similarity를 중심으로 추천합니다.\n")

    free_text = free_text_arg.strip() if free_text_arg else prompt_required("어떤 음악을 듣고 싶나요? > ")
    age = age_arg if age_arg is not None else prompt_age("나이 > ")
    genres = genres_arg if genres_arg is not None else split_user_values(input("선호 장르(선택, 쉼표/공백 구분) > "))
    artists = artists_arg if artists_arg is not None else split_user_values(input("선호 가수(선택, 쉼표/공백 구분) > "))

    songs = load_songs(catalog_path)
    embeddings = load_embedding_cache(embeddings_path)
    if not embeddings:
        raise MissingEmbeddingCacheError(f"임베딩 캐시가 비어 있습니다: {embeddings_path}")

    print("\n=== 추천 과정 ===")
    print(f"1. catalog 로드: {len(songs)}곡")
    print(f"2. lyrics embedding cache 로드: {len(embeddings)}곡")
    print(f"3. query text: {free_text}")
    print(f"4. age 입력: age={age}")
    preferred_year_center = preferred_year_center_arg
    if preferred_year_center is None:
        preferred_year_center = default_preferred_year_center()
    print(f"5. preferred year center: {preferred_year_center:.1f}")
    print(f"6. preference 입력: genres={genres or '없음'}, artists={artists or '없음'}")
    print("7. Upstage query embedding 생성 후 전체 곡의 lyrics similarity와 era_score 계산")

    engine = RecommendationEngine(songs, embeddings, UpstageEmbeddingClient())
    bundle = engine.recommend(
        RecommendationRequest(
            preferred_genres=genres,
            preferred_artists=artists,
            age=age,
            preferred_year_center=preferred_year_center,
            free_text=free_text,
            options={"bundle_size": bundle_size},
        )
    )
    print_bundle(bundle)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interactive recommendation demo")
    parser.add_argument("--catalog", default=DEFAULT_CATALOG_PATH.as_posix())
    parser.add_argument("--embeddings", default=DEFAULT_EMBEDDING_CACHE_PATH.as_posix())
    parser.add_argument("--bundle-size", type=int, default=6)
    parser.add_argument("--text", default="", help="Free text recommendation prompt. If omitted, prompts interactively.")
    parser.add_argument("--age", type=int, help="User age. If omitted, prompts interactively.")
    parser.add_argument("--preferred-year-center", type=float, help="Preferred release year center. Defaults to 2012.5.")
    parser.add_argument("--genres", nargs="*", help="Preferred genres. If omitted, prompts interactively.")
    parser.add_argument("--artists", nargs="*", help="Preferred artists. If omitted, prompts interactively.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run_interactive(
            Path(args.catalog),
            Path(args.embeddings),
            args.bundle_size,
            free_text_arg=args.text,
            age_arg=args.age,
            preferred_year_center_arg=args.preferred_year_center,
            genres_arg=args.genres,
            artists_arg=args.artists,
        )
    except (MissingEmbeddingCacheError, RecommendationInputError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
