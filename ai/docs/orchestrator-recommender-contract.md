# Orchestrator - Recommender 계약서

이 문서는 `orchestrator`와 `recommender`가 어떤 책임을 가지고, 어떤 JSON을 주고받아야 하는지를 정리한 계약서입니다.

## 1. 역할 분리

### Orchestrator가 담당하는 일
- 프론트엔드에서 온보딩 정보를 받는다.
- 사용자 피드백을 수집한다.
- 의미 없는 텍스트, 과도하게 편향된 피드백, 같은 아티스트에 대한 이상치 패턴을 걸러낸다.
- 이전 번들 결과와 사용자 피드백을 맥락 정보로 묶어 recommender에 다시 전달한다.
- recommender가 반환한 5곡이 규칙에 맞는지 1차 검증한다.
- 검증이 통과하면 사용자에게 전달한다.
- 검증이 통과하지 않으면 다시 recommender에 재요청한다.

### Recommender가 담당하는 일
- orchestrator가 전달한 기본 정보와 맥락 정보를 바탕으로 후보 풀을 만든다.
- 후보 20곡을 고른다.
- iTunes Search API로 검증한다.
- 라이브, 리마스터, instrumental, preview 없는 곡을 제외한다.
- 최종 5곡을 만든다.
- 선택 이유와 점수 정보를 구조화된 JSON으로 반환한다.

## 2. 전체 흐름

```text
프론트
  -> orchestrator
  -> recommender
  -> orchestrator 검증
  -> 프론트 사용자 전달
  -> 사용자 피드백 수집
  -> orchestrator 이상치 정리
  -> recommender 재요청
```

## 3. 1차 추천 흐름

### 3-1. 프론트 -> Orchestrator

프론트는 온보딩 정보를 orchestrator에 전달한다.

```json
{
  "user_id": "user_123",
  "session_id": "sess_abc",
  "age": 36,
  "preferred_genres": ["발라드"],
  "preferred_artists": ["조성모"],
  "free_text": "밤에 산책할 때 듣고 싶어요"
}
```

### 3-2. Orchestrator -> Recommender

orchestrator는 온보딩 정보와 세션 상태를 묶어 recommender에 전달한다.

```json
{
  "user_id": "user_123",
  "session_id": "sess_abc",
  "age": 36,
  "preferred_genres": ["발라드"],
  "preferred_artists": ["조성모"],
  "free_text": "밤에 산책할 때 듣고 싶어요",
  "context": {
    "bundle_id": "",
    "songs": [],
    "feedback_summary": {}
  },
  "context_text": "",
  "follow_up_text": "",
  "exclude_song_ids": [],
  "catalog_path": "ai/data/raw/melon_kpop_2000_2025.jsonl",
  "candidate_source": [],
  "expanded_preferred_genres": [],
  "expanded_preferred_artists": [],
  "preference_expansion": {},
  "negative_count": 0,
  "next_action": "recommend_next_bundle"
}
```

### 3-3. Recommender -> Orchestrator

recommender는 후보 풀 생성, 20곡 선택, iTunes 검증, 최종 5곡 선정을 거쳐 결과를 돌려준다.

```json
{
  "bundle_id": "bundle_ceaa556bb5d6",
  "emotion_title": "밤에 산책할 때 듣고 싶어요에 어울리는 추천 묶음",
  "songs": [
    {
      "song_id": "3849494",
      "title": "이등병의 편지",
      "artists": ["김광석"],
      "album": "김광석 '나의 노래' Box Set",
      "album_art_url": "https://is1-ssl.mzstatic.com/image/thumb/Music124/v4/f1/10/7a/f1107a1d-dff7-ead7-d98b-9b7211c001fb/jacket-3680.jpg/100x100bb.jpg",
      "preview_url": "https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview125/v4/80/12/b8/8012b869-3de2-e6a4-65ef-c5928c3f585b/mzaf_15841243184236533141.plus.aac.p.m4a",
      "slot_type": "anchor",
      "reason": "입력한 '밤에 산책할 때 듣고 싶어요'와 가사 분위기가 가까우면서 새롭게 느낄 수 있는 곡입니다.",
      "score_breakdown": {
        "theme": 0.6223,
        "era": 1.0,
        "discovery": 0.8,
        "quality": 0.4,
        "penalties": 0.0,
        "final": 0.7112
      }
    }
  ],
  "next_action": "collect_feedback"
}
```

### 3-4. Orchestrator의 검증

orchestrator는 recommender가 돌려준 5곡을 다음 기준으로 한 번 더 확인한다.

- 최종 개수가 5곡인지
- `preview_url`이 모두 있는지
- 라이브, 리마스터, instrumental 같은 변형 버전이 아닌지
- 중복 곡이 없는지
- 요청한 세션 정보와 맞는지

검증이 실패하면 recommender에 다시 요청한다.

## 4. 사용자 피드백 흐름

### 4-1. Orchestrator -> 프론트

orchestrator는 검증된 5곡을 사용자에게 보여준다.

### 4-2. 프론트 -> Orchestrator

사용자는 다음처럼 피드백을 줄 수 있다. `comment`는 곡별이 아닌 번들 전체에 대한 코멘트다.

```json
{
  "bundle_id": "bundle_ceaa556bb5d6",
  "comment": "조금 더 옛날 노래로 듣고 싶어요",
  "songs": [
    {
      "song_id": "3849494",
      "title": "이등병의 편지",
      "artists": ["김광석"],
      "reaction": "좋아요"
    },
    {
      "song_id": "82594",
      "title": "Blue Sky",
      "artists": ["박기영"],
      "reaction": "싫어요"
    }
  ]
}
```

### 4-3. Orchestrator의 이상치 처리

orchestrator는 아래 같은 이상치를 먼저 정리한다.

- 의미 없는 텍스트
  - 예: 무의미한 문자열, 반복 문자, 분석하기 어려운 짧은 텍스트
- 과도하게 편향된 피드백
  - 예: 동일 아티스트 곡을 거의 전부 좋아요 처리하고 한 곡만 싫어요로 주는 경우
- 사용자 의도와 맞지 않는 상충 피드백
  - 예: 같은 조건에서 매우 모순되는 평가가 반복되는 경우

이상치가 있으면 그대로 recommender에 넘기지 않고,
- 무시하거나
- 정규화하거나
- 추가 확인용 텍스트 질문으로 전환한다.

## 5. 다음 추천 흐름

사용자 피드백을 반영한 뒤 orchestrator는 이전 추천 결과와 피드백을 맥락으로 묶어 recommender에 다시 보낸다.

```json
{
  "user_id": "user_123",
  "session_id": "sess_abc",
  "age": 36,
  "preferred_genres": ["발라드"],
  "preferred_artists": ["조성모"],
  "free_text": "밤에 산책할 때 듣고 싶어요",
  "context": {
    "bundle_id": "bundle_ceaa556bb5d6",
    "songs": [
      {
        "song_id": "3849494",
        "title": "이등병의 편지",
        "artists": ["김광석"],
        "reaction": "좋아요"
      },
      {
        "song_id": "82594",
        "title": "Blue Sky",
        "artists": ["박기영"],
        "reaction": "싫어요"
      }
    ],
    "feedback_summary": {
      "comment": "조금 더 옛날 노래로 듣고 싶어요"
    }
  },
  "context_text": "{\"bundle_id\":\"bundle_ceaa556bb5d6\",\"songs\":[...],\"feedback_summary\":{\"comment\":\"조금 더 옛날 노래로 듣고 싶어요\"}}",
  "follow_up_text": "조금 더 옛날 노래로 듣고 싶어요",
  "exclude_song_ids": ["3849494", "82594"],
  "catalog_path": "ai/data/raw/melon_kpop_2000_2025.jsonl",
  "candidate_source": [],
  "expanded_preferred_genres": [],
  "expanded_preferred_artists": [],
  "preference_expansion": {},
  "negative_count": 1,
  "next_action": "recommend_next_bundle"
}
```

`follow_up_text`는 백엔드 세션에서 자동으로 채워진다. 프론트가 별도로 전달하지 않아도 된다.

## 6. 응답 JSON의 의미

| 필드 | 설명 |
|---|---|
| `bundle_id` | 추천 묶음 식별자 |
| `emotion_title` | 추천 묶음 제목 |
| `songs` | 최종 5곡 목록 |
| `album_art_url` | 앨범 이미지 URL |
| `preview_url` | 30초 미리듣기 URL |
| `slot_type` | `anchor` 또는 `discovery` |
| `reason` | 추천 이유 |
| `score_breakdown` | 선택 근거를 보여주는 점수 상세 |
| `next_action` | orchestrator가 다음에 해야 할 일 |

## 7. 구현 원칙

- `orchestrator`는 상태 관리, 이상치 처리, 검증, 사용자 전달을 담당한다.
- `recommender`는 후보 생성, LLM 선택, iTunes 검증, 최종 5곡 선택을 담당한다.
- 서로 주고받는 데이터는 JSON으로 고정한다.
- 최종 사용자에게 전달되는 곡 수는 5곡으로 고정한다.
- 사용자 피드백은 `좋아요 / 싫어요`를 기본으로 하되, 필요하면 추가 텍스트를 받는다.
