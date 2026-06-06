from __future__ import annotations

"""LangGraph 워크플로우용 오케스트레이터 노드 계약입니다.

이 모듈은 의도적으로 얇은 계약층으로만 유지합니다. 오케스트레이터
담당자는 함수 시그니처는 그대로 두고, 내부 구현만 실제 비즈니스
로직으로 채워 넣으면 됩니다. 그래야 추천 모듈이 같은 상태 구조에
계속 의존할 수 있습니다.
"""

from typing import Any, Callable, TypedDict

from .state import NextAction, RecommendationSessionState


FINAL_BUNDLE_SIZE = 5
CANDIDATE_POOL_SIZE = 20


class CandidateRecord(TypedDict, total=False):
    song_id: str
    title: str
    artists: list[str]
    album: str
    release_date: str | None
    release_year: int | None
    genres: list[str]
    like_count: int
    lyrics: str
    chart_appearances: list[dict[str, Any]]
    source_urls: dict[str, str]
    priority_score: float
    score_breakdown: dict[str, float]
    itunes_track_id: int
    preview_url: str
    album_art_url: str
    itunes_matched_by: str


CandidateSelector = Callable[
    [RecommendationSessionState, list[CandidateRecord], int],
    list[CandidateRecord],
]


def ingest_context(state: RecommendationSessionState) -> dict[str, Any]:
    # 오케스트레이터 담당자: 세션 입력을 정규화하고 context를 붙인 뒤
    # 다음 그래프 노드가 안전하게 사용할 수 있는 상태로 만들어 주세요.
    raise NotImplementedError("오케스트레이터 담당자가 ingest_context를 구현해야 합니다.")


def build_candidate_pool(state: RecommendationSessionState) -> dict[str, Any]:
    # 오케스트레이터 담당자: 카탈로그와 context를 바탕으로 후보 풀을 구성해 주세요.
    raise NotImplementedError("오케스트레이터 담당자가 build_candidate_pool를 구현해야 합니다.")


def llm_select_20_candidates(state: RecommendationSessionState) -> dict[str, Any]:
    # 오케스트레이터 담당자: 프롬프트 기반 LLM을 호출해 후보 20곡을 골라 주세요.
    raise NotImplementedError("오케스트레이터 담당자가 llm_select_20_candidates를 구현해야 합니다.")


def verify_with_itunes(state: RecommendationSessionState) -> dict[str, Any]:
    # 오케스트레이터 담당자: 미리듣기 불가 곡과 라이브/리마스터 변형을 걸러 주세요.
    raise NotImplementedError("오케스트레이터 담당자가 verify_with_itunes를 구현해야 합니다.")


def select_final_5(state: RecommendationSessionState) -> dict[str, Any]:
    # 오케스트레이터 담당자: 검증이 끝난 곡들 중에서 최종 5곡만 남겨 주세요.
    raise NotImplementedError("오케스트레이터 담당자가 select_final_5를 구현해야 합니다.")


def collect_feedback(state: RecommendationSessionState) -> dict[str, Any]:
    # 오케스트레이터 담당자: 좋아요/싫어요를 집계해서 세션 상태를 갱신해 주세요.
    raise NotImplementedError("오케스트레이터 담당자가 collect_feedback를 구현해야 합니다.")


def decide_next_action(state: RecommendationSessionState) -> dict[str, Any]:
    # 오케스트레이터 담당자: 갱신된 상태를 바탕으로 다음 그래프 분기를 결정해 주세요.
    raise NotImplementedError("오케스트레이터 담당자가 decide_next_action를 구현해야 합니다.")


def route_after_feedback(state: RecommendationSessionState) -> NextAction:
    # 오케스트레이터 담당자: 조건부 엣지에서 사용할 라우트 키를 반환해 주세요.
    raise NotImplementedError("오케스트레이터 담당자가 route_after_feedback를 구현해야 합니다.")
