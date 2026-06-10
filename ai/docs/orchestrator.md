# Orchestrator 설계 및 구글시트 연동 가이드

## 1. 역할 분리

### Orchestrator가 담당하는 일

- 프론트엔드에서 온보딩 정보를 받는다.
- 사용자 피드백을 수집한다.
- 의미 없는 텍스트, 과도하게 편향된 피드백, 같은 아티스트에 대한 이상치 패턴을 걸러낸다.
- 이전 번들 결과와 사용자 피드백을 맥락 정보로 묶어 recommender에 다시 전달한다.
- recommender가 반환한 5곡이 규칙에 맞는지 1차 검증한다.
- 검증이 통과하면 사용자에게 전달한다.
- 검증이 통과하지 않으면 다시 recommender에 재요청한다.
- 구글시트에 사용자 입력 기록 및 곡 카탈로그 조회

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
  → Orchestrator
  → Recommender
  → Orchestrator 검증
  → 프론트 사용자 전달
  → 사용자 피드백 수집
  → Orchestrator 이상치 정리
  → Recommender 재요청
```

## 3. 디렉토리 구조

```
ai/orchestrator/
├── __init__.py
├── sheets_client.py       # Google Sheets 읽기/쓰기
├── input_collector.py     # 온보딩 입력 수집 + 시트 저장
├── session_context.py     # 세션 상태 관리 (bundle 이력, exclude_song_ids 등)
├── outlier_filter.py      # 이상치 처리 (의미없는 텍스트, 편향 피드백)
├── bundle_validator.py    # Recommender 결과 5곡 검증
└── orchestrator.py        # 메인 흐름 제어
```

## 4. 주고받는 JSON

### 4-1. 프론트 → Orchestrator (온보딩)

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

### 4-2. Orchestrator → Recommender (1차 추천 요청)

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

### 4-3. Recommender → Orchestrator (추천 결과)

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
      "album_art_url": "https://is1-ssl.mzstatic.com/image/thumb/.../100x100bb.jpg",
      "preview_url": "https://audio-ssl.itunes.apple.com/...",
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

### 4-4. Orchestrator 검증 기준

recommender가 돌려준 5곡을 다음 기준으로 확인한다.

| 검증 항목 | 내용 |
|-----------|------|
| 곡 수 | 최종 개수가 5곡인지 |
| preview_url | 모두 존재하는지 |
| 변형 버전 | 라이브, 리마스터, instrumental이 아닌지 |
| 중복 | 동일 곡이 없는지 |
| 세션 일치 | 요청한 세션 정보와 맞는지 |

검증 실패 시 recommender에 재요청한다.

### 4-5. 프론트 → Orchestrator (사용자 피드백)

`comment`는 곡별이 아닌 번들 전체에 대한 코멘트다.

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

### 4-6. Orchestrator 이상치 처리

다음 패턴을 감지하면 그대로 recommender에 넘기지 않는다.

| 유형 | 예시 | 처리 |
|------|------|------|
| 의미 없는 텍스트 | 무의미한 문자열, 반복 문자 | 무시 |
| 과도하게 편향된 피드백 | 동일 아티스트 곡 전부 좋아요 후 한 곡만 싫어요 | 정규화 |
| 상충 피드백 | 같은 조건에서 모순된 평가 반복 | 추가 확인 질문으로 전환 |

### 4-7. Orchestrator → Recommender (다음 추천 요청)

피드백 반영 후 이전 번들과 피드백을 맥락으로 묶어 전달한다.

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
  "context_text": "{\"bundle_id\":\"bundle_ceaa556bb5d6\",\"songs\":[...],\"feedback_summary\":{\"comment\":\"...\"}}",
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

## 5. 응답 JSON 필드 설명

| 필드 | 설명 |
|------|------|
| `bundle_id` | 추천 묶음 식별자 |
| `emotion_title` | 추천 묶음 제목 |
| `songs` | 최종 5곡 목록 |
| `album_art_url` | 앨범 이미지 URL |
| `preview_url` | 30초 미리듣기 URL |
| `slot_type` | `anchor` 또는 `discovery` |
| `reason` | 추천 이유 |
| `score_breakdown` | 선택 근거를 보여주는 점수 상세 |
| `next_action` | orchestrator가 다음에 해야 할 일 |

## 6. 구현 원칙

- orchestrator는 상태 관리, 이상치 처리, 검증, 사용자 전달을 담당한다.
- recommender는 후보 생성, LLM 선택, iTunes 검증, 최종 5곡 선택을 담당한다.
- 서로 주고받는 데이터는 JSON으로 고정한다.
- 최종 사용자에게 전달되는 곡 수는 5곡으로 고정한다.
- 사용자 피드백은 좋아요 / 싫어요를 기본으로 하되, 필요하면 추가 텍스트를 받는다.

---

## 7. Google Cloud 서비스 계정 설정

### 7.1 프로젝트 생성 및 API 활성화

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 상단 프로젝트 선택 → **새 프로젝트** 생성
3. 좌측 메뉴 **API 및 서비스 → 라이브러리** 이동
4. `Google Sheets API` 검색 → **사용 설정**
5. `Google Drive API` 검색 → **사용 설정** (gspread 내부 동작에 필요)

### 7.2 서비스 계정 생성

1. 좌측 메뉴 **API 및 서비스 → 사용자 인증 정보** 이동
2. **사용자 인증 정보 만들기 → 서비스 계정** 선택
3. 서비스 계정 이름 입력 (예: `sw-maestro-sheets`) → **만들기 및 계속**
4. 역할은 **기본 → 편집자** 선택 → **계속 → 완료**
5. 생성된 서비스 계정 클릭 → **키** 탭 → **키 추가 → 새 키 만들기 → JSON** 선택
6. JSON 파일이 자동 다운로드됨 → `service_account.json`으로 이름 변경

### 7.3 JSON 키 파일 배치

```
ai/
└── credentials/
    └── service_account.json   ← 절대 git에 커밋하지 않음
```

`ai/.gitignore`에 `credentials/` 추가 필요 (완료됨).

### 7.4 구글 시트 공유 설정

1. 스프레드시트 열기 → **공유** 클릭
2. `service_account.json`의 `client_email` 값 입력
3. 권한 **편집자** → **보내기**

---

## 8. 구글시트 구조

### 8.1 UserInput 시트

| timestamp | user_id | session_id | age | preferred_genres | preferred_artists | free_text |
|-----------|---------|------------|-----|-----------------|-------------------|-----------|
| 2026-06-07T10:00:00 | user_123 | sess_abc | 24 | 댄스,R&B | NewJeans,태연 | 밤에 산책할 때 들을 노래 |

### 8.2 SongCatalog 시트

기존 `data/raw/melon_kpop_2000_2025.jsonl`과 동일한 필드 구조를 사용한다.

| song_id | title | artist | genre | year | lyrics_preview |
|---------|-------|--------|-------|------|----------------|

---

## 9. 스프레드시트 정보

| 항목 | 값 |
|------|-----|
| Spreadsheet ID | `1E8_Q4uat1TWR9_HjrNwOH-Zb3oVSoMyf_fByEorsmdE` |
| UserInput 시트 | 온보딩 입력값 기록 |
| SongCatalog 시트 | 곡 목록 조회 |

## 10. Python 패키지

```bash
pip install gspread google-auth
```

---

## 11. 구현 현황

| 항목 | 상태 |
|------|------|
| Google Cloud 프로젝트 생성 | ✅ |
| Sheets API / Drive API 활성화 | ✅ |
| 서비스 계정 JSON 키 발급 | ✅ (`ai/credentials/service_account.json`) |
| 구글시트 공유 설정 | ✅ |
| `sheets_client.py` 구현 | ✅ |
| `input_collector.py` 구현 | ✅ |
| 동작 테스트 | ✅ (`save_user_input` 호출 → UserInput 시트 기록 확인) |
| `session_context.py` 구현 | ✅ |
| `outlier_filter.py` 구현 | ✅ |
| `bundle_validator.py` 구현 | ✅ |
| `orchestrator.py` 구현 | ✅ |
