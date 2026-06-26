from unittest import TestCase

from analysis.authorship.metrics import prepare_authorship_payload


class TestAuthorshipMetrics(TestCase):
    def test_prepare_authorship_payload_precomputes_collaboration_metric_ranks(self):
        network_data = {
            "nodes": [
                {"id": "1", "author": ["Alice", "Bob"]},
                {"id": "2", "author": ["Alice", "Carol"]},
                {"id": "3", "author": ["Bob", "Carol"]},
                {"id": "4", "author": ["Alice"]},
            ]
        }

        payload = prepare_authorship_payload(network_data)
        rows = {
            row["author"]: row
            for row in payload["collaboration_metrics_rows"]
        }

        self.assertIn("rawDegreeRank", rows["Alice"])
        self.assertIn("weightedDegreeRank", rows["Alice"])
        self.assertIn("weightedEigenvectorRank", rows["Alice"])
        self.assertIn("betweennessRank", rows["Alice"])
        self.assertEqual(rows["Alice"]["rawDegree"], 2)
        self.assertEqual(rows["Bob"]["rawDegree"], 2)
        self.assertEqual(rows["Carol"]["rawDegree"], 2)
        self.assertEqual(rows["Alice"]["weightedDegreeRank"], 1)
        self.assertEqual(rows["Bob"]["weightedDegreeRank"], 1)
        self.assertEqual(rows["Carol"]["weightedDegreeRank"], 1)
        self.assertIn("collaboration_metrics_summary", payload)
        self.assertIn("collaboration_cluster_size_distribution", payload)
        self.assertIn("collaboration_degree_distribution", payload)
