# Backend (FastAPI)

향수곡 추천 서비스의 백엔드. **오케스트레이터(`ai/orchestrator/`) 추천 파이프라인을
HTTP로 감싸** Flutter 프론트엔드에 노출하고, 세션 상태를 관리한다.

## 역할 경계 (orchestrator-recommender-contract.md 기준)

```text
프론트(Flutter) → [Backend: FastAPI] → orchestrator 노드 → recommender(LLM/iTunes)
```

- **Backend (이 디렉토리)**: HTTP 엔드포인트, 세션 상태 저장, 카탈로그 로드, 파이프라인 구동/조립
- **Orchestrator (`ai/orchestrator/`)**: LangGraph 그래프 + 노드(ingest → pool → LLM선별 → iTunes검증 → 최종5곡 → 피드백)
- **Recommender (`ai/recommender/`)**: 후보 풀, LLM 후보 선별, iTunes 검증, 최종 선정

> 추천 1턴은 HTTP 요청/응답 단위로 나눠 실행한다(LangGraph 그래프를 통째로 돌리지 않고
> 노드 함수를 순서대로 호출). 피드백은 별도 요청에서 `collect_feedback → decide_next_action`을 돈다.

## 구조

```text
backend/
├── app/
│   ├── main.py                  # FastAPI 앱 + 시작 시 카탈로그 1회 로드(lifespan)
│   ├── config.py                # 환경변수 설정
│   ├── schemas.py               # 요청/응답 Pydantic 모델
│   ├── deps.py                  # 의존성 주입
│   ├── session_store.py         # 인메모리 세션 상태(회원 DB는 추후 교체)
│   ├── orchestrator_service.py  # 추천 파이프라인 구동 + 번들 조립
│   └── routers/
│       ├── sessions.py          POST /sessions
│       ├── recommendations.py   POST /recommendations
│       ├── feedbacks.py         POST /feedbacks
│       └── library.py           GET  /sessions/{id}/library
└── tests/test_api.py            # 네트워크/키 없이 도는 통합 테스트(가짜 LLM 주입)
```

## 실행

repo 루트에서 실행한다(`ai` 패키지가 루트에 있으므로).

```bash
cd backend && pip install -r requirements.txt && cd ..
cp backend/.env.example backend/.env

# repo 루트에서:
PYTHONPATH=backend:. AI_SKIP_ITUNES_VERIFICATION=1 AI_SKIP_PREFERENCE_EXPANSION=1 \
  uvicorn app.main:app --reload --app-dir backend
```

- Swagger 문서: http://127.0.0.1:8000/docs
- `PYTHONPATH=backend:.` → `app`(backend)과 `ai`(루트) 둘 다 import.

> **실제 추천에는 Upstage 키가 필요**하다(`ai/.env`의 `UPSTAGE_API_KEY`).
> LLM 후보 선별(`llm_select_20_candidates`)이 Upstage Solar를 호출한다.
> 키/네트워크 없이 구동하려면 위 두 `AI_SKIP_*` 환경변수를 켠다(검증/선호확장 건너뜀).

## Docker 배포

빌드 컨텍스트는 **repo 루트**다(`ai/` 와 `backend/` 둘 다 필요).

```bash
# repo 루트에서:
docker build -f backend/Dockerfile -t soma-backend .
docker run --rm -p 8000:8000 \
  -e UPSTAGE_API_KEY=$UPSTAGE_API_KEY \
  soma-backend
```

docker compose 사용:

```bash
cd backend
UPSTAGE_API_KEY=... docker compose up --build
# 키 없이 띄워보기(검증/선호확장 스킵):
AI_SKIP_ITUNES_VERIFICATION=1 AI_SKIP_PREFERENCE_EXPANSION=1 docker compose up --build
```

- 헬스체크: `GET /health`
- API 전체 명세: [docs/API.md](docs/API.md)

## 테스트

```bash
python3 -m pytest backend/tests -q
```

가짜 LLM 선별기 주입 + iTunes/선호확장 스킵으로 전체 흐름을 네트워크 없이 검증한다.

## API 흐름

```text
POST /sessions        온보딩(나이/장르/선호가수) → session_id
POST /recommendations free_text → ingest→pool→LLM선별→iTunes검증→최종5곡 → 번들
                      (추천 곡은 exclude_song_ids에 누적)
POST /feedbacks       곡별 좋아요/싫어요 → negative_count/exclude 갱신 → next_action
                      (싫어요 3회 → request_follow_up_text), saved 곡은 보관함行
GET  /sessions/{id}/library   보관함 곡
```

reaction 값은 `좋아요` / `싫어요` 두 가지다(추천모듈 `Feedback` 계약).

## 남은 작업(TODO)

- 회원 영속화(DB) — 현재는 인메모리. `SessionStore`만 교체.
- `select_final_5`는 번들 곡 리스트만 만든다 → `bundle_id`/`emotion_title`은 백엔드가 조립 중.
  (오케스트레이터 측에 bundle 조립이 생기면 그쪽으로 위임)
- Flutter 프론트(`feat/ui` 브랜치)의 mock repository를 이 API로 교체 연결.

## 참고: ai 모듈 순환 import 수정

`ai/recommender/engine.py`가 `ai.orchestrator.state`를 런타임 import 하고,
`ai.orchestrator`는 다시 engine을 import 해서 `import ai.recommender` 단독이 깨지는
순환 버그가 있었다. engine의 해당 import를 `TYPE_CHECKING` 전용으로 옮겨 고쳤다.
(AI 모듈 담당자와 공유 필요)
