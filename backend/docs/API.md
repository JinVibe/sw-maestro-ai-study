# 백엔드 API 문서

향수곡 추천 서비스 백엔드(FastAPI)의 전체 엔드포인트 / 요청 / 응답 / 스키마 명세.

- Base URL (로컬): `http://127.0.0.1:8000`
- 모든 본문은 `application/json` (UTF-8, 한글 그대로).
- 대화형 문서: `GET /docs` (Swagger), `GET /redoc`

## 흐름 요약

```text
1) POST /sessions                        온보딩 → session_id 발급
2) POST /recommendations                 free_text → 5곡 번들
3) 사용자가 곡마다 좋아요/싫어요
4) POST /feedbacks                       반응 전송 → next_action 결정
   ├─ next_action=recommend_next_bundle
   │    → 2)로 반복 (free_text 생략 가능, 이전 피드백 자동 반영)
   └─ next_action=request_follow_up_text
        → 5) 팔로업 텍스트 입력 후 2)로 반복
5) POST /sessions/{id}/follow-up         팔로업 텍스트 저장 → next_action: recommend_next_bundle
6) GET  /sessions/{id}/library           저장(saved)한 곡 목록
```

세션 상태(`exclude_song_ids`, `negative_count`, `next_action`, `follow_up_text`, 선호 정보)는 백엔드가 서버 메모리에 보관한다. 클라이언트는 `session_id`만 들고 다니면 된다.

---

## 1. POST /sessions — 온보딩

세션을 만든다. `preferred_year_center`는 받지 않는다(추천 모듈이 `age`로 계산).

### Request `CreateSessionRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `age` | int (1–120) | ✅ | 나이 |
| `preferred_genres` | string[] | | 선호 장르 |
| `preferred_artists` | string[] | | 선호 아티스트 |
| `user_id` | string | | 회원 식별자(비회원은 빈 값) |

```json
{
  "age": 36,
  "preferred_genres": ["발라드"],
  "preferred_artists": ["조성모"],
  "user_id": ""
}
```

### Response 200 `SessionResponse`

```json
{
  "session_id": "sess_0a1b2c3d4e5f",
  "user_id": "",
  "age": 36,
  "preferred_genres": ["발라드"],
  "preferred_artists": ["조성모"],
  "next_action": "recommend_next_bundle"
}
```

---

## 2. POST /sessions/{session_id}/follow-up — 팔로업 텍스트

싫어요 3개 이상으로 `next_action=request_follow_up_text`가 된 뒤, 사용자 코멘트를 저장한다.
저장된 텍스트는 다음 `POST /recommendations` 호출 시 AI에 자동 전달된다.

### Request `FollowUpRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `text` | string (≥1) | ✅ | 사용자 추가 의견 |

```json
{ "text": "신나는 댄스 음악이 좋아요" }
```

### Response 200 `FollowUpResponse`

```json
{ "next_action": "recommend_next_bundle" }
```

### 오류

| 코드 | 상황 |
| --- | --- |
| 404 | `session_id` 없음 |

---

## 3. POST /recommendations — 추천

세션 정보 + 현재 테마(`free_text`)로 5곡 번들을 만든다.
내부 파이프라인: `ingest → 후보풀 → LLM 20곡 선별 → iTunes 검증 → 최종 5곡`.

두 번째 번들부터는 `free_text`를 생략할 수 있다. 이전 피드백 컨텍스트와 `follow_up_text`가 세션에서 자동으로 반영된다.

### Request `RecommendRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `session_id` | string | ✅ | `/sessions`에서 받은 값 |
| `free_text` | string | | 현재 듣고 싶은 느낌/상황 (첫 요청 권장, 이후 생략 가능) |

```json
{
  "session_id": "sess_0a1b2c3d4e5f",
  "free_text": "밤에 산책할 때 듣고 싶어요"
}
```

두 번째 번들 이후 (피드백 제공 후):
```json
{
  "session_id": "sess_0a1b2c3d4e5f"
}
```

### Response 200 `BundleResponse`

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `bundle_id` | string | 번들 식별자(피드백 때 다시 보냄) |
| `emotion_title` | string | 감성 타이틀 |
| `songs` | `RecommendedSong[]` | 추천 곡(보통 5곡) |
| `next_action` | string | `collect_feedback` |

`RecommendedSong`:

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `song_id` | string | 곡 ID |
| `title` | string | 곡명 |
| `artists` | string[] | 아티스트명 |
| `album` | string | 앨범명 |
| `album_art_url` | string | 앨범 아트(iTunes, 검증 스킵 시 빈 값) |
| `preview_url` | string | 30초 미리듣기(iTunes, 검증 스킵 시 빈 값) |
| `slot_type` | string | `anchor` / `discovery` 등 |
| `reason` | string | 추천 사유 |

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
      "album_art_url": "https://.../100x100bb.jpg",
      "preview_url": "https://.../preview.m4a",
      "slot_type": "anchor",
      "reason": "입력한 '밤에 산책할 때 듣고 싶어요'와 분위기가 가까운 곡입니다."
    }
  ],
  "next_action": "collect_feedback"
}
```

### 오류

| 코드 | 상황 |
| --- | --- |
| 404 | `session_id` 없음 |
| 422 | 후보 부족 / 입력 오류 |

---

## 4. POST /feedbacks — 피드백

곡별 반응과 번들 코멘트를 보내 다음 행동을 결정한다.

### Request `FeedbackRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `session_id` | string | ✅ | 세션 |
| `bundle_id` | string | | 피드백 대상 번들(생략 시 마지막 번들) |
| `comment` | string | | 번들 전체에 대한 코멘트 |
| `feedbacks` | `FeedbackItem[]` | ✅ | 곡별 반응 |

`FeedbackItem`:

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `song_id` | string | ✅ | 곡 ID |
| `title` | string | | 곡명(선택) |
| `artists` | string[] | | 아티스트(선택) |
| `reaction` | `"좋아요"` \| `"싫어요"` | ✅ | 반응 |
| `saved` | bool | | 보관함 저장 여부 |

```json
{
  "session_id": "sess_0a1b2c3d4e5f",
  "bundle_id": "bundle_ceaa556bb5d6",
  "comment": "전반적으로 너무 옛날 노래였어요",
  "feedbacks": [
    { "song_id": "3849494", "reaction": "좋아요", "saved": true },
    { "song_id": "708211", "reaction": "싫어요" }
  ]
}
```

### Response 200 `FeedbackResponse`

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `negative_count` | int | 이번 번들 싫어요 수 |
| `next_action` | string | 아래 표 참고 |

`next_action` 값:

| 값 | 의미 |
| --- | --- |
| `recommend_next_bundle` | 바로 다음 추천 가능 |
| `request_follow_up_text` | 싫어요 3회 이상 → 팔로업 텍스트 필요 |
| `finish` | 종료 |

```json
{ "negative_count": 1, "next_action": "recommend_next_bundle" }
```

부수효과: 반응을 준 곡은 `exclude_song_ids`에 누적되어 다음 추천에서 제외된다. `saved=true` 곡은 보관함에 들어간다. `comment`는 세션에 저장되어 다음 추천 시 AI에 자동 전달된다.

### 오류

| 코드 | 상황 |
| --- | --- |
| 404 | `session_id` 없음 |
| 422 | 잘못된 `reaction` |

---

## 5. GET /sessions/{session_id}/library — 보관함

`saved=true`로 저장한 곡 목록.

### Response 200 `LibraryResponse`

```json
{
  "session_id": "sess_0a1b2c3d4e5f",
  "songs": [
    {
      "song_id": "3849494",
      "title": "이등병의 편지",
      "artists": ["김광석"],
      "album": "김광석 '나의 노래' Box Set",
      "album_art_url": "https://.../100x100bb.jpg",
      "preview_url": "https://.../preview.m4a",
      "slot_type": "anchor",
      "reason": "..."
    }
  ]
}
```

### 오류

| 코드 | 상황 |
| --- | --- |
| 404 | `session_id` 없음 |

---

## 6. GET /health

```json
{ "status": "ok" }
```

---

## 부록: 환경 변수

| 변수 | 기본 | 설명 |
| --- | --- | --- |
| `CATALOG_PATH` | `ai/data/raw/melon_kpop_2000_2025.jsonl` | 후보 카탈로그 경로 |
| `UPSTAGE_API_KEY` | (없음) | 실제 추천(LLM 후보 선별)에 필요, `ai/.env`에 설정 |
| `AI_SKIP_ITUNES_VERIFICATION` | `0` | `1`이면 iTunes 검증 스킵(키/네트워크 불필요) |
| `AI_SKIP_PREFERENCE_EXPANSION` | `0` | `1`이면 선호 확장 LLM 호출 스킵 |
| `AI_SKIP_LLM_SELECTION` | `0` | `1`이면 LLM 후보 선별 스킵(테스트용) |

## 부록: curl 예시

```bash
BASE=http://127.0.0.1:8000

SID=$(curl -s $BASE/sessions -H 'Content-Type: application/json' \
  -d '{"age":36,"preferred_genres":["발라드"],"preferred_artists":["조성모"]}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['session_id'])")

# 첫 번째 추천
curl -s $BASE/recommendations -H 'Content-Type: application/json' \
  -d "{\"session_id\":\"$SID\",\"free_text\":\"밤에 산책할 때 듣고 싶어요\"}"

# 피드백
curl -s $BASE/feedbacks -H 'Content-Type: application/json' \
  -d "{\"session_id\":\"$SID\",\"comment\":\"좋았어요\",\"feedbacks\":[{\"song_id\":\"3849494\",\"reaction\":\"좋아요\",\"saved\":true}]}"

# 두 번째 추천 (free_text 생략)
curl -s $BASE/recommendations -H 'Content-Type: application/json' \
  -d "{\"session_id\":\"$SID\"}"

# 싫어요 3개 이상 후 팔로업 텍스트 입력
curl -s $BASE/sessions/$SID/follow-up -H 'Content-Type: application/json' \
  -d '{"text":"신나는 댄스 음악이 좋아요"}'

curl -s $BASE/sessions/$SID/library
```
