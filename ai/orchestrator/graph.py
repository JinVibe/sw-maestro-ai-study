from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

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


@dataclass(frozen=True, slots=True)
class OrchestratorGraphSkeleton:
    nodes: tuple[str, ...]
    edges: Mapping[str, tuple[str, ...]]
    conditional_routes: Mapping[str, tuple[NextAction, ...]]
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
            "recommend_next_bundle": ("build_candidate_pool",),
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
    )


def build_recommendation_graph():
    """노드 본문이 채워지면 바로 실행 가능한 LangGraph 그래프를 만듭니다."""

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
            "recommend_next_bundle": "build_candidate_pool",
            "request_follow_up_text": END,
            "finish": END,
        },
    )
    return workflow.compile()


def describe_recommendation_graph() -> str:
    skeleton = build_recommendation_graph_skeleton()
    lines = [
        "추천 오케스트레이터 그래프 뼈대:",
        "  START -> ingest_context -> build_candidate_pool -> llm_select_20_candidates",
        "  -> verify_with_itunes -> select_final_5 -> collect_feedback -> decide_next_action",
        "  decide_next_action 라우트: recommend_next_bundle -> build_candidate_pool | request_follow_up_text -> END | finish -> END",
        f"  candidate_pool_size={skeleton.candidate_pool_size}",
        f"  final_bundle_size={skeleton.final_bundle_size}",
    ]
    return "\n".join(lines)
