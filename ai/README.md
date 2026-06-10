# AI Recommendation Module

AI Agent 기반 음악 추천 서비스의 추천 모듈 작업 공간입니다.

이 디렉토리는 AI 담당자가 소유합니다. `frontend/`, `backend/`, 최상위 `README.md`는 팀 합의가 있을 때만 수정합니다.

## Directory

```text
ai/
├── README.md
├── docs/
│   ├── backend-agent-integration.md
│   └── recommendation-module.md
├── scripts/
│   └── melon_scraper.py
├── recommender/
│   ├── catalog.py
│   ├── cli.py
│   ├── embedding_store.py
│   ├── engine.py
│   ├── feedback.py
│   ├── models.py
│   ├── scoring.py
│   └── upstage_client.py
├── data/
│   ├── raw/
│   │   ├── .gitkeep
│   │   └── melon_kpop_2000_2025.jsonl
│   └── embeddings/
│       └── .gitkeep
├── tests/
│   └── .gitkeep
└── .gitignore
```

## Data Policy

실서비스에서 쓰는 원천 데이터는 `ai/data/raw/`에 둡니다.

대용량 원본 데이터는 GitHub에 올리지 않고 Google Drive로 공유합니다. 팀원이 새로 clone한 뒤에는 Drive에서 원본 데이터를 내려받아 `ai/data/raw/`에 넣으면 됩니다.

원본 데이터 예시:

- `ai/data/raw/melon_kpop_2000_2025.jsonl`
- `ai/data/raw/oh_my_memory.sqlite`
- `ai/data/raw/*.partial`
- `ai/data/raw/*.tmp`
- `ai/data/raw/*.state.json`
- `ai/data/raw/*.errors`

현재 Google Drive 링크는 아직 확정 전입니다. 링크가 준비되면 아래 형식으로 문서에 추가합니다.

```text
Google Drive: <원본 데이터 공유 폴더 링크>
Local path: ai/data/raw/
```

## Catalog Data

추천 모듈 개발과 서비스 실행은 기본적으로 `ai/data/raw/melon_kpop_2000_2025.jsonl`을 사용합니다.

```text
ai/data/raw/melon_kpop_2000_2025.jsonl
```

원본 JSONL은 `ai/data/raw/`에 두고, 추천 품질 검증과 실제 서비스 실험은 이 파일을 기준으로 진행합니다.

## Upstage Solar Embeddings

추천 모듈 v1은 Upstage Solar Embeddings를 사용합니다. 곡은 가사만 임베딩하고, 사용자 쿼리는 `--text`로 받은 free text만 임베딩합니다.

추천 실행에는 `--text`와 `--age`가 필수입니다. `--age`는 추천 모듈이 초기 `preferred_year_center`를 계산하는 기준 정보입니다. 곡을 하드 필터링하지 않고, 발매연도와 계산된 중심 연도의 거리를 `era_score`로 계산해 최종 점수에 반영합니다.

초기 `preferred_year_center`는 외부 입력으로 받지 않습니다. 추천 모듈이 `age`로 출생연도를 추정하고, 데이터 범위 2000~2025년에서의 `user_age_at_release` 중간값을 다시 연도로 환산해 계산합니다. 예를 들어 2026년 기준 36세 사용자는 출생연도 1990년, 2000~2025년 발매곡 기준 나이 범위 10~35세, 중간값 22.5세이므로 초기 중심 연도는 `2012.5`입니다.

이후 피드백에서 시대 선호를 바꿀지는 agent 모듈이 판단하고, 추천 모듈에는 `era_shift` 숫자로 넘깁니다. `era_shift=0`이면 초기값 또는 현재 값을 유지하고, `era_shift=-n`이면 중심 연도를 `n`만큼 낮추며, `era_shift=n`이면 중심 연도를 `n`만큼 높입니다.

백엔드/Agent 연동 시에는 다음 세션 상태를 유지한 뒤 다음 추천 요청에 다시 넘깁니다.

```text
preferred_year_center
strategy_weights
unknown_streak
exclude_song_ids
```

피드백 처리는 `ai.recommender.feedback.process_feedback(...)`를 사용합니다. Agent는 유저 코멘트를 해석해 `era_shift`만 결정하고, 추천 모듈은 이 값을 그대로 반영합니다.

```python
from ai.recommender.feedback import process_feedback

updated = process_feedback(
    feedbacks=feedbacks,
    preferred_year_center=session.preferred_year_center,
    age=session.age,
    era_shift=-4,
    previous_unknown_streak=session.unknown_streak,
)
```

다음 추천에는 `updated.preferred_year_center`와 Agent가 계산한 full `strategy_weights`를 `RecommendationRequest`에 넣습니다. 추천 모듈은 피드백으로 가중치를 학습하지 않고, Agent가 넘긴 가중치를 검증/정규화만 합니다.

v1.1 추천 흐름:

```text
온보딩 기반 후보 필터링
→ 필터링된 후보의 누락 가사 임베딩 생성/캐시 저장
→ final_score 계산
→ 5~7곡 bundle 생성
```

Agent 가중치 형식:

```json
{
  "w_theme": 0.50,
  "w_era": 0.20,
  "w_discovery": 0.20,
  "w_quality": 0.10
}
```

백엔드/Agent 연동용 상세 입출력 계약은 `ai/docs/backend-agent-integration.md`를 참고합니다.

- 곡 가사 임베딩: `solar-embedding-1-large-passage`
- 사용자 free text 임베딩: `solar-embedding-1-large-query`
- 캐시 위치: `ai/data/embeddings/lyrics_embeddings.jsonl`

API 키는 `ai/.env`에 저장합니다. 이 파일은 GitHub에 올리지 않습니다.

```text
UPSTAGE_API_KEY=your-api-key
```

곡 가사 임베딩 캐시 생성:

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m ai.recommender.cli embed-songs --input ai/data/raw/melon_kpop_2000_2025.jsonl --output ai/data/embeddings/lyrics_embeddings.jsonl --batch-size 32
```

추천 실행:

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m ai.recommender.cli recommend --catalog ai/data/raw/melon_kpop_2000_2025.jsonl --embeddings ai/data/embeddings/lyrics_embeddings.jsonl --genres 발라드 --artists 조성모 --text "밤에 산책할 때 듣고 싶어요" --age 36 --bundle-size 6
```

피드백 이후 재추천처럼 전략 가중치를 명시적으로 넘길 수도 있습니다.

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m ai.recommender.cli recommend --catalog ai/data/raw/melon_kpop_2000_2025.jsonl --embeddings ai/data/embeddings/lyrics_embeddings.jsonl --text "밤에 산책할 때 듣고 싶어요" --age 36 --strategy-weights '{"w_theme":0.50,"w_era":0.20,"w_discovery":0.20,"w_quality":0.10}' --bundle-size 6
```

추천 실행에는 fallback 문장을 사용하지 않습니다.

전체 임베딩 캐시는 GitHub에 올리지 않습니다. 팀 공유가 필요하면 원본 데이터와 함께 Google Drive에 공유합니다.

## Melon Scraper

Melon 시대별 차트의 2000~2025년 국내 K-pop Top100 곡 메타데이터를 수집해 곡 중심 JSONL로 저장하는 Python 유틸리티입니다.

수집 항목:

- 차트 정보: 연도, 순위, 곡ID, 곡명, 아티스트, 앨범, 앨범ID
- 상세 정보: 발매일, 장르, FLAC, 좋아요수, 가사 전문
- 추천서비스용 중복 처리: 같은 `songId`는 한 줄로 병합하고 `chartAppearances`에 연도/순위를 누적

실행:

```powershell
python ai/scripts/melon_scraper.py --start-year 2000 --end-year 2025 --output ai/data/raw/melon_kpop_2000_2025.jsonl
```

Codex 번들 Python을 직접 사용할 때:

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' ai/scripts/melon_scraper.py --start-year 2000 --end-year 2025 --output ai/data/raw/melon_kpop_2000_2025.jsonl
```

기본적으로 수집 중간마다 체크포인트를 씁니다.

- 최종 결과: `ai/data/raw/melon_kpop_2000_2025.jsonl`
- 중간 저장: `ai/data/raw/melon_kpop_2000_2025.jsonl.partial`
- 실패 로그: `ai/data/raw/melon_kpop_2000_2025.jsonl.errors`
- 현재 위치: `ai/data/raw/melon_kpop_2000_2025.jsonl.state.json`

중간에 중단되면 같은 명령을 다시 실행하면 체크포인트를 읽고 이어서 진행합니다. 체크포인트를 무시하고 처음부터 다시 수집하려면 `--no-resume`을 추가하세요.

샘플 검증용으로 한 해만 수집하려면:

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' ai/scripts/melon_scraper.py --start-year 2000 --end-year 2000 --output ai/data/raw/melon_kpop_2000_sample.jsonl --sleep 0.2
```

차단 응답으로 보이는 `403`, `406`, `429`가 나오면 현재 연도/순위/곡ID를 state 파일에 저장하고 기본 300초 대기 후 같은 곡을 한 번 다시 시도합니다. 더 천천히 수집하려면 `--sleep`, `--jitter`, `--block-cooldown`을 늘리세요.

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' ai/scripts/melon_scraper.py --start-year 2000 --end-year 2025 --output ai/data/raw/melon_kpop_2000_2025.jsonl --sleep 5 --jitter 5 --block-cooldown 900
```

## GitHub Workflow

기본 협업 방식은 브랜치와 Pull Request입니다.

권장 브랜치:

- `feature/ai-recommendation-structure`
- `feature/ai-recommendation-engine`
- `docs/ai-module-design`

작업 흐름:

```powershell
git clone https://github.com/JinVibe/sw-maestro-ai-study.git
cd sw-maestro-ai-study
git checkout -b feature/ai-recommendation-structure
```

변경 후에는 사용자 승인 후에만 Git 명령어를 실행합니다.

```powershell
git status
git add ai/
git commit -m "chore(ai): set up recommendation module workspace"
git push origin feature/ai-recommendation-structure
```

`main` 브랜치에는 직접 push하지 않습니다. 작업 브랜치를 push한 뒤 GitHub에서 Pull Request를 생성합니다.

## Tests

기본 테스트는 네트워크 없이 실행됩니다. Upstage API 호출은 CLI 수동 실행에서만 발생합니다.

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s ai/tests
```
