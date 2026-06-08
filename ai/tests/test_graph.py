from __future__ import annotations

import unittest

from ai.orchestrator.graph import build_recommendation_graph, build_recommendation_graph_skeleton


class GraphTest(unittest.TestCase):
    def test_recommendation_graph_smoke(self) -> None:
        skeleton = build_recommendation_graph_skeleton()
        graph = build_recommendation_graph()

        self.assertIn("build_candidate_pool", skeleton.nodes)
        self.assertIn("select_final_5", skeleton.nodes)
        self.assertIsNotNone(graph)


if __name__ == "__main__":
    unittest.main()
