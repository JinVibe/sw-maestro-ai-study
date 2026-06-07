# Flutter Frontend

Music recommendation frontend for the SW Maestro AI study project.

## Setup

```bash
flutter pub get
flutter run
```

If platform folders are not present yet, generate them inside this directory:

```bash
flutter create . --platforms=android,web
```

## 백엔드 API 연동

이 앱은 FastAPI 백엔드(`../backend`)를 호출한다.
먼저 백엔드를 띄운다(repo 루트에서):

```bash
PYTHONPATH=backend:. uvicorn app.main:app --reload --app-dir backend
```

그리고 앱 실행 시 백엔드 주소를 `--dart-define`으로 넘긴다.

```bash
# Android 에뮬레이터(호스트 localhost = 10.0.2.2, 기본값)
flutter run

# iOS 시뮬레이터 / 웹 / 데스크톱
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000

# 실기기(같은 와이파이의 PC IP)
flutter run --dart-define=API_BASE_URL=http://192.168.0.10:8000
```

연동 흐름:

```text
온보딩(나이/장르/가수) → POST /sessions (session_id 발급)
추천 화면 진입        → POST /recommendations (장르 기반 free_text) → 카드 5곡
좋아요/글쎄요 스와이프  → POST /feedbacks (좋아요=저장, 글쎄요=싫어요)
큐 소진               → 다음 번들 자동 요청
글쎄요 3연속          → 꼬리 질문 시트 → follow_up_text로 재추천
```

연동 코드:

- `lib/core/api/api_config.dart` — 베이스 URL(`API_BASE_URL`로 덮어쓰기)
- `lib/features/recommendation/data/api_recommendations_repository.dart` — HTTP 호출 + 매핑
- `lib/features/recommendation/presentation/recommendation_controller.dart` — 세션 생성/추천/피드백 상태

> 실제 추천(LLM 후보 선별)에는 백엔드에 `UPSTAGE_API_KEY`가 필요하다.
> 메모: 온보딩에 "지금 듣고 싶은 느낌" 입력이 없어 현재는 장르로 free_text를 만든다(컨트롤러 TODO).
> `mock_recommendations_repository.dart`는 오프라인 참고용으로 남겨둔 더미다(현재 미사용).

## Structure

```text
lib/
|-- app/                  # App shell and routing entry
|-- core/                 # Shared theme/constants
`-- features/
    `-- recommendation/
        |-- data/         # Mock/API data sources
        |-- domain/       # Feature entities
        `-- presentation/ # State, pages, widgets
```
