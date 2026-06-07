"""Orchestrator 대화형 데모 스크립트.

실행:
    python -m ai.scripts.orchestrator_demo
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.orchestrator import Orchestrator
from ai.orchestrator.recommender_adapter import build_engine, make_recommender_fn
from ai.recommender.errors import MissingEmbeddingCacheError


# ------------------------------------------------------------------ #
# Mock Recommender
# ------------------------------------------------------------------ #

_MOCK_SONGS = [
    {"song_id": "001", "title": "이등병의 편지",   "artists": ["김광석"], "album": "나의 노래",       "album_art_url": "https://example.com/art1.jpg",  "preview_url": "https://example.com/p1.m4a",  "slot_type": "anchor",    "reason": "free_text와 분위기가 가장 가까운 곡",  "score_breakdown": {"theme": 0.62, "era": 1.00, "discovery": 0.8, "quality": 0.4, "penalties": 0.0, "final": 0.71}},
    {"song_id": "002", "title": "가을 아침",        "artists": ["아이유"], "album": "Palette",         "album_art_url": "https://example.com/art2.jpg",  "preview_url": "https://example.com/p2.m4a",  "slot_type": "theme_match","reason": "잔잔한 밤 산책 분위기",               "score_breakdown": {"theme": 0.58, "era": 0.90, "discovery": 0.7, "quality": 0.5, "penalties": 0.0, "final": 0.67}},
    {"song_id": "003", "title": "사랑하기 때문에",  "artists": ["유재하"], "album": "사랑하기 때문에", "album_art_url": "https://example.com/art3.jpg",  "preview_url": "https://example.com/p3.m4a",  "slot_type": "era_fit",   "reason": "선호 연도대 대표곡",                  "score_breakdown": {"theme": 0.50, "era": 1.00, "discovery": 0.6, "quality": 0.6, "penalties": 0.0, "final": 0.65}},
    {"song_id": "004", "title": "빗속에서",         "artists": ["신승훈"], "album": "신승훈 1집",     "album_art_url": "https://example.com/art4.jpg",  "preview_url": "https://example.com/p4.m4a",  "slot_type": "discovery", "reason": "잘 알려지지 않은 발견 곡",            "score_breakdown": {"theme": 0.45, "era": 0.80, "discovery": 1.0, "quality": 0.4, "penalties": 0.0, "final": 0.63}},
    {"song_id": "005", "title": "기억의 습작",      "artists": ["015B"],   "album": "015B 2집",       "album_art_url": "https://example.com/art5.jpg",  "preview_url": "https://example.com/p5.m4a",  "slot_type": "theme_match","reason": "밤 감성과 맞는 발라드",               "score_breakdown": {"theme": 0.48, "era": 0.85, "discovery": 0.7, "quality": 0.5, "penalties": 0.0, "final": 0.62}},
    {"song_id": "006", "title": "너에게",           "artists": ["조성모"], "album": "To Heaven",      "album_art_url": "https://example.com/art6.jpg",  "preview_url": "https://example.com/p6.m4a",  "slot_type": "anchor",    "reason": "선호 아티스트 대표곡",                "score_breakdown": {"theme": 0.55, "era": 0.90, "discovery": 0.5, "quality": 0.7, "penalties": 0.0, "final": 0.66}},
    {"song_id": "007", "title": "To Heaven",        "artists": ["조성모"], "album": "To Heaven",      "album_art_url": "https://example.com/art7.jpg",  "preview_url": "https://example.com/p7.m4a",  "slot_type": "theme_match","reason": "선호 아티스트 수록곡",                "score_breakdown": {"theme": 0.52, "era": 0.88, "discovery": 0.5, "quality": 0.65,"penalties": 0.0, "final": 0.64}},
    {"song_id": "008", "title": "J에게",            "artists": ["이문세"], "album": "이문세 3집",     "album_art_url": "https://example.com/art8.jpg",  "preview_url": "https://example.com/p8.m4a",  "slot_type": "era_fit",   "reason": "80년대 감성 대표곡",                  "score_breakdown": {"theme": 0.50, "era": 1.00, "discovery": 0.6, "quality": 0.65,"penalties": 0.0, "final": 0.65}},
    {"song_id": "009", "title": "붉은 노을",        "artists": ["이문세"], "album": "이문세 5집",     "album_art_url": "https://example.com/art9.jpg",  "preview_url": "https://example.com/p9.m4a",  "slot_type": "theme_match","reason": "노을 감성과 맞는 발라드",             "score_breakdown": {"theme": 0.53, "era": 0.95, "discovery": 0.6, "quality": 0.60,"penalties": 0.0, "final": 0.64}},
    {"song_id": "010", "title": "걱정말아요 그대",  "artists": ["이적"],   "album": "Homme",          "album_art_url": "https://example.com/art10.jpg", "preview_url": "https://example.com/p10.m4a", "slot_type": "discovery", "reason": "위로가 되는 산책 음악",               "score_breakdown": {"theme": 0.56, "era": 0.85, "discovery": 0.9, "quality": 0.60,"penalties": 0.0, "final": 0.67}},
]

def mock_recommender(request: dict) -> dict:
    exclude = set(request.get("exclude_song_ids", []))
    available = [s for s in _MOCK_SONGS if s["song_id"] not in exclude]
    chosen = available[:5]
    return {
        "bundle_id": f"bundle_mock_{len(exclude):03d}",
        "emotion_title": f"{request.get('free_text', '')}에 어울리는 추천 묶음",
        "songs": chosen,
        "next_action": "collect_feedback",
    }


# ------------------------------------------------------------------ #
# 입력 헬퍼
# ------------------------------------------------------------------ #

def prompt(msg: str, default: str = "") -> str:
    value = input(msg).strip()
    return value if value else default

def prompt_int(msg: str) -> int:
    while True:
        value = input(msg).strip()
        if value.isdigit() and int(value) > 0:
            return int(value)
        print("  숫자로 입력해주세요. 예: 36")

def prompt_list(msg: str) -> list[str]:
    value = input(msg).strip()
    if not value:
        return []
    return [v.strip() for v in value.replace(",", " ").split() if v.strip()]

def print_bundle(bundle: dict) -> None:
    print(f"\nbundle_id : {bundle['bundle_id']}")
    print(f"제목      : {bundle['emotion_title']}")
    for i, song in enumerate(bundle["songs"], 1):
        sb = song["score_breakdown"]
        print(f"\n  {i}. {song['title']} - {', '.join(song['artists'])}")
        print(f"     이유  : {song['reason']}")
        print(f"     점수  : final={sb['final']:.2f}  theme={sb['theme']:.2f}  era={sb['era']:.2f}")

def prompt_feedback(bundle: dict) -> dict:
    print("\n각 곡에 피드백을 입력하세요 (1=좋아요, 2=싫어요, Enter=좋아요)")
    songs_feedback = []
    for song in bundle["songs"]:
        reaction_input = prompt(f"  [{song['title']}] 1/2 > ", default="1")
        reaction = "싫어요" if reaction_input == "2" else "좋아요"
        comment = ""
        if reaction == "싫어요":
            comment = prompt("  코멘트 (선택) > ")
        songs_feedback.append({
            "song_id": song["song_id"],
            "title": song["title"],
            "artists": song["artists"],
            "reaction": reaction,
            "comment": comment,
        })
    return {"bundle_id": bundle["bundle_id"], "songs": songs_feedback}


# ------------------------------------------------------------------ #
# 메인
# ------------------------------------------------------------------ #

def collect_onboarding() -> dict:
    mode = prompt("\n입력 방식 선택 (1=JSON 붙여넣기, 2=항목별 입력, Enter=1) > ", default="1")

    if mode == "2":
        user_id    = prompt("user_id (Enter = user_123) > ", default="user_123")
        session_id = prompt("session_id (Enter = 자동생성) > ", default=f"sess_{uuid.uuid4().hex[:6]}")
        age        = prompt_int("나이 > ")
        genres     = prompt_list("선호 장르 (쉼표/공백 구분, 없으면 Enter) > ")
        artists    = prompt_list("선호 가수 (쉼표/공백 구분, 없으면 Enter) > ")
        free_text  = prompt("어떤 음악을 듣고 싶나요? > ")
        return {
            "user_id": user_id,
            "session_id": session_id,
            "age": age,
            "preferred_genres": genres,
            "preferred_artists": artists,
            "free_text": free_text,
        }

    print("JSON을 붙여넣고 빈 줄에서 Enter를 두 번 누르세요:")
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    return json.loads("\n".join(lines))


def main() -> None:
    print("=" * 50)
    print("  Orchestrator 대화형 데모")
    print("=" * 50)

    onboarding = collect_onboarding()

    use_real = prompt("\n실제 추천 AI 사용? (Enter=예, m=mock) > ", default="real")
    if use_real.lower() == "m":
        recommender_fn = mock_recommender
        print("mock 추천 AI 사용")
    else:
        try:
            catalog_path = onboarding.get("catalog_path", "ai/data/samples/melon_kpop_sample.jsonl")
            print(f"추천 AI 로딩 중... (catalog: {catalog_path})")
            engine = build_engine(catalog_path=catalog_path)
            recommender_fn = make_recommender_fn(engine)
            print("실제 추천 AI 로드 완료")
        except (MissingEmbeddingCacheError, FileNotFoundError) as e:
            print(f"실제 AI 로드 실패: {e}\nmock으로 대체합니다.")
            recommender_fn = mock_recommender

    orch = Orchestrator(recommender_fn=recommender_fn)

    # 1차 추천
    print("\n[1차 추천 결과]")
    bundle = orch.start_session(onboarding)
    print_bundle(bundle)

    # 피드백 루프
    while True:
        print("\n")
        go = prompt("피드백을 입력하시겠어요? (Enter=예, q=종료) > ")
        if go.lower() == "q":
            break

        feedback = prompt_feedback(bundle)
        result = orch.process_feedback(feedback)

        if result.get("next_action") == "follow_up":
            print(f"\n[추가 질문] {result['follow_up_question']}")
            break

        print("\n[다음 추천 결과]")
        bundle = result
        print_bundle(bundle)

    # 세션 상태 출력
    ctx = orch._context
    print("\n[세션 상태]")
    print(f"  들은 곡 수    : {len(ctx.exclude_song_ids)}곡")
    print(f"  싫어요 횟수   : {ctx.negative_count}")
    print(f"  follow_up_text: {ctx.follow_up_text or '없음'}")
    print(f"  번들 이력     : {len(ctx.bundle_history)}회")
    print("\n구글시트에 데이터가 저장되었습니다.")


if __name__ == "__main__":
    main()
