from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import (
    CANDIDATE_POOL_SIZE,
    FINAL_BUNDLE_SIZE,
    build_candidate_pool,
    collect_feedback,
    decide_next_action,
    ingest_context,
    llm_select_20_candidates,
    route_after_feedback,
    select_final_5,
    verify_with_itunes,
)
from .state import NextAction, RecommendationSessionState

_INTERRUPT_AFTER = ("select_final_5",)


@dataclass(frozen=True, slots=True)
class OrchestratorGraphSkeleton:
    nodes: tuple[str, ...]
    edges: Mapping[str, tuple[str, ...]]
    conditional_routes: Mapping[str, tuple[NextAction, ...]]
    interrupt_after: tuple[str, ...] = field(default=_INTERRUPT_AFTER)
    candidate_pool_size: int = CANDIDATE_POOL_SIZE
    final_bundle_size: int = FINAL_BUNDLE_SIZE


def build_recommendation_graph_skeleton() -> OrchestratorGraphSkeleton:
    return OrchestratorGraphSkeleton(
        nodes=(
            "ingest_context",
            "build_candidate_pool",
            "llm_select_20_candidates",
            "verify_with_itunes",
            "select_final_5",
            "collect_feedback",
            "decide_next_action",
        ),
        edges={
            "START": ("ingest_context",),
            "ingest_context": ("build_candidate_pool",),
            "build_candidate_pool": ("llm_select_20_candidates",),
            "llm_select_20_candidates": ("verify_with_itunes",),
            "verify_with_itunes": ("select_final_5",),
            "select_final_5": ("collect_feedback",),
            "collect_feedback": ("decide_next_action",),
            "recommend_next_bundle": ("ingest_context",),
            "request_follow_up_text": ("END",),
            "finish": ("END",),
        },
        conditional_routes={
            "decide_next_action": (
                "recommend_next_bundle",
                "request_follow_up_text",
                "finish",
            ),
        },
        interrupt_after=_INTERRUPT_AFTER,
    )


def build_recommendation_graph(checkpointer=None):
    """select_final_5 이후 interrupt하는 LangGraph 그래프를 빌드합니다.

    checkpointer가 없으면 MemorySaver를 기본으로 사용합니다.
    같은 thread_id로 resume_with_feedback을 호출하려면 동일한 checkpointer를 공유해야 합니다.
    """
    workflow = StateGraph(RecommendationSessionState)
    workflow.add_node("ingest_context", ingest_context)
    workflow.add_node("build_candidate_pool", build_candidate_pool)
    workflow.add_node("llm_select_20_candidates", llm_select_20_candidates)
    workflow.add_node("verify_with_itunes", verify_with_itunes)
    workflow.add_node("select_final_5", select_final_5)
    workflow.add_node("collect_feedback", collect_feedback)
    workflow.add_node("decide_next_action", decide_next_action)

    workflow.add_edge(START, "ingest_context")
    workflow.add_edge("ingest_context", "build_candidate_pool")
    workflow.add_edge("build_candidate_pool", "llm_select_20_candidates")
    workflow.add_edge("llm_select_20_candidates", "verify_with_itunes")
    workflow.add_edge("verify_with_itunes", "select_final_5")
    workflow.add_edge("select_final_5", "collect_feedback")
    workflow.add_edge("collect_feedback", "decide_next_action")

    workflow.add_conditional_edges(
        "decide_next_action",
        route_after_feedback,
        {
            "recommend_next_bundle": "ingest_context",
            "request_follow_up_text": END,
            "finish": END,
        },
    )

    return workflow.compile(
        checkpointer=checkpointer if checkpointer is not None else MemorySaver(),
        interrupt_after=list(_INTERRUPT_AFTER),
    )


def start_recommendation(
    initial_state: RecommendationSessionState,
    thread_id: str,
    graph=None,
) -> list[dict[str, Any]]:
    """온보딩 입력을 받아 최초 5곡을 선택하고 반환합니다.

    그래프는 select_final_5 완료 후 중단(interrupt)되어 피드백 대기 상태가 됩니다.
    이후 resume_with_feedback으로 재개할 때 동일한 graph 인스턴스와 thread_id를 사용해야 합니다.
    """
    if graph is None:
        graph = build_recommendation_graph()
    config = {"configurable": {"thread_id": thread_id}}
    graph.invoke(initial_state, config)
    snapshot = graph.get_state(config)
    return list(snapshot.values.get("final_bundle") or [])


def resume_with_feedback(
    context_with_reactions: dict[str, Any],
    thread_id: str,
    graph,
) -> dict[str, Any]:
    """피드백이 담긴 context를 state에 반영하고 그래프를 재개합니다.

    Args:
        context_with_reactions: 사용자 반응이 포함된 context
            예: {"bundle_id": "...", "songs": [{"song_id": "...", "reaction": "좋아요", ...}, ...]}
        thread_id: start_recommendation에서 사용한 동일 thread_id
        graph: start_recommendation에서 사용한 동일 graph 인스턴스

    Returns:
        {
            "final_bundle": list[dict],  # 다음 5곡 (recommend_next_bundle인 경우)
            "next_action": str,          # "recommend_next_bundle" | "request_follow_up_text" | "finish"
        }
    """
    config = {"configurable": {"thread_id": thread_id}}
    graph.update_state(config, {"context": context_with_reactions})
    graph.invoke(None, config)
    snapshot = graph.get_state(config)
    state = snapshot.values
    return {
        "final_bundle": list(state.get("final_bundle") or []),
        "next_action": str(state.get("next_action") or "recommend_next_bundle"),
    }


def describe_recommendation_graph() -> str:
    skeleton = build_recommendation_graph_skeleton()
    lines = [
        "추천 오케스트레이터 그래프 뼈대:",
        "  START -> ingest_context -> build_candidate_pool -> llm_select_20_candidates",
        "  -> verify_with_itunes -> [interrupt] select_final_5 -> collect_feedback -> decide_next_action",
        "  decide_next_action 라우트: recommend_next_bundle -> build_candidate_pool | request_follow_up_text -> END | finish -> END",
        f"  interrupt_after={skeleton.interrupt_after}",
        f"  candidate_pool_size={skeleton.candidate_pool_size}",
        f"  final_bundle_size={skeleton.final_bundle_size}",
    ]
    return "\n".join(lines)
