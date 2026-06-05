# Backend and Agent Integration Guide

이 문서는 백엔드 팀원과 Agent 팀원이 추천 모듈 v1.1을 연결할 때 필요한 입출력 계약과 피드백 처리 흐름을 정리한다.

## 1. 역할 분리

```text
Client
  - 온보딩 입력 수집
  - 추천 결과 표시
  - 곡별 반응, 별점, 코멘트, 저장 여부 수집

Backend
  - 세션/회원별 추천 상태 저장
  - RecommendationEngine 초기화와 호출
  - 추천 결과의 score_breakdown 보관
  - 추천 결과 song_id를 다음 추천 exclude_song_ids에 반영

Agent Orchestrator
  - 사용자 free_text와 피드백 코멘트 해석
  - era_shift 결정
  - strategy_weights 결정
  - follow_up_question 문장 생성

AI Recommender
  - 온보딩 기반 후보 사전 필터링
  - 필터링된 후보의 누락 가사 임베딩 생성/캐시 저장
  - final_score 기준 bundle 생성
  - preferred_year_center, unknown_streak, next_action 업데이트
```

## 2. 백엔드 세션 상태

회원은 DB에 저장하고, 비회원은 세션 저장소에 둔다.

```json
{
  "user_id": "user_123",
  "session_id": "sess_abc",
  "age": 36,
  "preferred_genres": ["발라드"],
  "preferred_artists": ["조성모"],
  "preferred_year_center": null,
  "strategy_weights": {
    "w_theme": 0.50,
    "w_era": 0.20,
    "w_discovery": 0.20,
    "w_quality": 0.10
  },
  "unknown_streak": 0,
  "exclude_song_ids": []
}
```

초기값:

| 필드 | 초기값 |
| --- | --- |
| `preferred_year_center` | `null`. 첫 추천 시 추천 모듈이 `age`로 계산한다. |
| `strategy_weights.w_theme` | `0.50` |
| `strategy_weights.w_era` | `0.20` |
| `strategy_weights.w_discovery` | `0.20` |
| `strategy_weights.w_quality` | `0.10` |
| `unknown_streak` | `0` |
| `exclude_song_ids` | `[]` |

## 3. 추천 요청

클라이언트 입력 예시:

```json
{
  "user_id": "user_123",
  "session_id": "sess_abc",
  "age": 36,
  "preferred_genres": ["발라드"],
  "preferred_artists": ["조성모"],
  "free_text": "밤에 산책할 때 듣고 싶어요",
  "bundle_size": 6
}
```

백엔드는 세션 상태와 클라이언트 입력을 합쳐 `RecommendationRequest`를 만든다.

```python
from ai.recommender.models import RecommendationRequest

request = RecommendationRequest(
    user_id=session.user_id,
    session_id=session.session_id,
    age=session.age,
    preferred_year_center=session.preferred_year_center,
    preferred_genres=session.preferred_genres,
    preferred_artists=session.preferred_artists,
    free_text=free_text,
    exclude_song_ids=session.exclude_song_ids,
    strategy_weights=session.strategy_weights,
    options={"bundle_size": bundle_size},
)
```

필수값:

| 필드 | 설명 |
| --- | --- |
| `age` | 현재 v1.1에서 필수 입력이다. |
| `free_text` | 사용자 상황/감성 요청. 비어 있으면 추천 오류가 난다. |
| `strategy_weights` | 없으면 기본값을 사용한다. 있으면 정확히 4개 key가 필요하다. |

`preferred_year_center`는 클라이언트 온보딩 입력으로 받지 않는다. 세션에 값이 없으면 추천 모듈이 `age`로 출생연도를 추정하고, 데이터 범위 2000~2025년에서의 `user_age_at_release` 중간값을 다시 연도로 환산해 계산한다. 예를 들어 2026년 기준 36세 사용자는 출생연도 1990년, 2000~2025년 발매곡 기준 나이 범위 10~35세, 중간값 22.5세이므로 초기 중심 연도는 `2012.5`가 된다.

Agent가 넘기는 `strategy_weights`는 full 형태여야 한다.

```json
{
  "w_theme": 0.50,
  "w_era": 0.20,
  "w_discovery": 0.20,
  "w_quality": 0.10
}
```

추천 모듈은 음수, 누락 key, 추가 key, 합 0을 거부한다. 합이 1이 아니면 내부에서 정규화한다.

## 4. 추천 실행

서비스 시작 시 카탈로그와 임베딩 캐시는 한 번 로드해 재사용하는 방식을 권장한다.

```python
from pathlib import Path

from ai.recommender.catalog import load_songs
from ai.recommender.embedding_store import load_embedding_cache
from ai.recommender.engine import RecommendationEngine
from ai.recommender.upstage_client import UpstageEmbeddingClient

cache_path = Path("ai/data/embeddings/lyrics_embeddings.jsonl")
songs = load_songs(Path("ai/data/raw/melon_kpop_2000_2025.jsonl.partial"))
embeddings = load_embedding_cache(cache_path)

engine = RecommendationEngine(
    songs=songs,
    embeddings=embeddings,
    embedding_client=UpstageEmbeddingClient(),
    embedding_cache_path=cache_path,
    embedding_batch_size=32,
)

bundle = engine.recommend(request)
response = bundle.to_dict()
```

추천 모듈 내부 흐름:

```text
1. free_text query embedding 생성
2. age로 초기 preferred_year_center를 계산하고, preferred_genres, preferred_artists, exclude_song_ids와 함께 후보 사전 필터링
3. 후보 중 캐시에 없거나 가사 hash/model/source가 다른 곡만 Upstage passage embedding 생성
4. 생성한 임베딩을 메모리와 lyrics_embeddings.jsonl에 저장
5. final_score 기준으로 bundle 구성
```

사전 필터링 정책:

```text
preferred_year_center ± 8년 우선
→ 부족하면 ±12.5년
→ 부족하면 시대 조건 완화
→ 장르/아티스트 선호 후보가 부족하면 전체 후보로 완화
```

장르/아티스트는 점수 보너스가 아니라 후보 필터링에만 사용한다.

## 5. 추천 응답

```json
{
  "bundle_id": "bundle_0516889bd960",
  "emotion_title": "밤에 산책할 때 듣고 싶어요에 어울리는 추천 묶음",
  "songs": [
    {
      "song_id": "708211",
      "title": "Mr. Flower",
      "artists": ["조성모"],
      "album": "My First",
      "album_art_url": "",
      "preview_url": "",
      "slot_type": "anchor",
      "reason": "입력한 '밤에 산책할 때 듣고 싶어요'와 가사 분위기가 가깝고 선호 시대와도 맞는 곡입니다.",
      "score_breakdown": {
        "theme": 0.639,
        "era": 0.72,
        "discovery": 0.45,
        "quality": 0.4,
        "penalties": 0.0,
        "final": 0.701
      }
    }
  ],
  "next_action": "collect_feedback"
}
```

주의:

- `album_art_url`, `preview_url`은 현재 v1.1에서 빈 값이다.
- 프론트 표시용 미디어 URL은 별도 수집/매핑 단계가 필요하다.
- `score_breakdown`은 피드백 처리용으로 백엔드가 보관한다.

## 6. Agent 피드백 해석

클라이언트 피드백 예시:

```json
{
  "bundle_id": "bundle_0516889bd960",
  "feedbacks": [
    {
      "song_id": "708211",
      "reaction": "듣고 싶어요",
      "rating": 5,
      "comment": "이런 옛날 발라드 더 듣고 싶어요",
      "saved": true
    }
  ]
}
```

허용 reaction:

```text
알아요
듣고 싶어요
몰라요
```

Agent Orchestrator는 코멘트와 대화 맥락을 보고 다음 값을 결정한다.

| 값 | Agent 책임 |
| --- | --- |
| `era_shift` | 선호 연도 중심을 얼마나 이동할지 결정 |
| `strategy_weights` | 다음 추천에서 theme/era/discovery/quality를 얼마나 볼지 결정 |
| follow-up question text | `next_action`이 `follow_up_question`일 때 사용자 질문 생성 |

`era_shift` 권장 v1.1 규칙:

```text
오래된/추억/예전/레트로 흐름을 명시 -> -4
최신/요즘/최근/신곡 흐름을 명시 -> 4
시대 언급 없음 -> 0
강한 표현이면 -8 또는 8 사용 가능
```

추천 모듈은 `era_shift`를 `2000~2025` 범위 안에서 자동 보정한다.

## 7. 피드백 처리

추천 모듈은 피드백으로 strategy weight를 학습하지 않는다. Agent가 다음 `strategy_weights`를 계산한다.

백엔드는 추천 응답에 있던 `score_breakdown`을 `Feedback`에 붙일 수 있지만, v1.1 추천 모듈은 이를 weight learning에 사용하지 않는다.

```python
from ai.recommender.feedback import process_feedback
from ai.recommender.models import Feedback

feedbacks = [
    Feedback(
        song_id=item["song_id"],
        reaction=item["reaction"],
        rating=item["rating"],
        comment=item.get("comment", ""),
        saved=item.get("saved", False),
        score_breakdown=recommended_song_score_breakdown,
        slot_type=recommended_song_slot_type,
    )
    for item in client_feedbacks
]

updated = process_feedback(
    feedbacks=feedbacks,
    preferred_year_center=session.preferred_year_center,
    age=session.age,
    era_shift=agent_era_shift,
    previous_unknown_streak=session.unknown_streak,
)
```

`process_feedback` 결과:

```json
{
  "preferred_year_center": 2008.5,
  "unknown_streak": 0,
  "next_action": "recommend_next_bundle"
}
```

백엔드는 이 값을 세션에 저장한다.

```python
session.preferred_year_center = updated.preferred_year_center
session.unknown_streak = updated.unknown_streak
session.strategy_weights = agent_strategy_weights
session.exclude_song_ids.extend([song["song_id"] for song in bundle_response["songs"]])
```

## 8. 재추천

다음 추천 요청에는 업데이트된 상태를 그대로 넣는다.

```python
next_request = RecommendationRequest(
    user_id=session.user_id,
    session_id=session.session_id,
    age=session.age,
    preferred_year_center=session.preferred_year_center,
    preferred_genres=session.preferred_genres,
    preferred_artists=session.preferred_artists,
    free_text=next_free_text,
    exclude_song_ids=session.exclude_song_ids,
    strategy_weights=session.strategy_weights,
    options={"bundle_size": 6},
)
```

`next_action` 처리:

| 값 | 백엔드/Agent 행동 |
| --- | --- |
| `recommend_next_bundle` | 바로 재추천 가능 |
| `follow_up_question` | Agent가 꼬리 질문을 먼저 생성 |

`몰라요`가 3회 연속이면 `follow_up_question`이 반환된다.

## 9. 전체 데이터 준비

전체 데이터 추천 품질 테스트에는 원본 카탈로그와 전체 임베딩 캐시가 필요하다.

```text
ai/data/raw/melon_kpop_2000_2025.jsonl.partial
ai/data/embeddings/lyrics_embeddings.jsonl
```

전체 임베딩 캐시 생성:

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m ai.recommender.cli embed-songs --input ai/data/raw/melon_kpop_2000_2025.jsonl.partial --output ai/data/embeddings/lyrics_embeddings.jsonl --batch-size 32
```

전체 데이터 추천 실행:

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m ai.recommender.cli recommend --catalog ai/data/raw/melon_kpop_2000_2025.jsonl.partial --embeddings ai/data/embeddings/lyrics_embeddings.jsonl --genres 발라드 --artists 조성모 --text "밤에 산책할 때 듣고 싶어요" --age 36 --strategy-weights '{"w_theme":0.50,"w_era":0.20,"w_discovery":0.20,"w_quality":0.10}' --bundle-size 6
```

원본 데이터와 전체 임베딩 캐시는 GitHub에 올리지 않는다. Google Drive 같은 공유 저장소로 전달한다.
