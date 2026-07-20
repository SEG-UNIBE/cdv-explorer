from unittest import TestCase

from analysis.authorship.metrics import (
    extract_authorship_metrics,
    prepare_authorship_payload,
)


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
        rows = {row["author"]: row for row in payload["collaboration_metrics_rows"]}

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

    def test_prepare_authorship_payload_includes_git_contributor_aggregates(self):
        network_data = {
            "nodes": [
                {"id": "1", "author": ["Alice"], "contributors": ["Alice", "Dana"]},
                {"id": "2", "author": ["Bob"], "contributors": ["Dana", "Eve"]},
                {"id": "3", "author": ["Alice", "Carol"], "contributors": []},
            ]
        }
        contributor_metrics = extract_authorship_metrics(
            network_data["nodes"],
            field="contributors",
            include_network=False,
        )

        payload = prepare_authorship_payload(
            network_data,
            contributor_metrics=contributor_metrics,
        )

        contributors = payload["contributors"]
        self.assertNotIn("collaboration_network", contributors)
        self.assertEqual(
            contributors["top_contributors"][0],
            {"author": "Dana", "count": 2},
        )
        self.assertEqual(
            contributors["coverage"],
            {
                "contributor_count": 3,
                "declared_author_count": 3,
                "contributors_also_declared": 1,
                "contributors_never_declared": 2,
                "proposals_with_git_data": 2,
                "proposals_with_uncredited": 1,
            },
        )

    def test_extract_authorship_metrics_sorts_tied_top_authors_by_name(self):
        nodes = [
            {"id": "1", "author": ["Zoe"]},
            {"id": "2", "author": ["Alice"]},
            {"id": "3", "author": ["Murch"]},
            {"id": "4", "author": ["Alice"]},
            {"id": "5", "author": ["Zoe"]},
        ]

        metrics = extract_authorship_metrics(nodes)

        self.assertEqual(
            metrics["top_authors"][:3],
            [
                {"author": "Alice", "count": 2},
                {"author": "Zoe", "count": 2},
                {"author": "Murch", "count": 1},
            ],
        )
