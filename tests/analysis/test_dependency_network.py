import unittest

from analysis.dependencies.metrics import build_graph, extract_dependency_metrics
from analysis.dependencies.network import build_network_data
from analysis.pipeline import combined_source_key, merge_source_network_data
from analysis.validation.ground_truth import (
    load_ground_truth_curated_entries,
    validate_ground_truth_curated_entries,
)
from ecosystems import ECOSYSTEM_REGISTRY
from pipeline.source_context import SourceContext
from tests.helpers import proposal as _proposal


class BuildNetworkDataTests(unittest.TestCase):
    def test_link_created_when_both_nodes_exist(self):
        result = build_network_data([_proposal("1", regex_refs=["BIP 2"]), _proposal("2")],
                                    id_field="bip", proposal_label="BIP")
        edges = result["dependency_edges"]
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["source"], "bips:1")
        self.assertEqual(edges[0]["target"], "bips:2")
        self.assertEqual(edges[0]["extraction_method"], "body_extracted_regex")
        self.assertNotIn("links", result)

    def test_generator_input_still_creates_edges(self):
        proposals = (_proposal(value, regex_refs=["BIP 2"] if value == "1" else []) for value in ["1", "2"])

        result = build_network_data(proposals, id_field="bip", proposal_label="BIP")

        self.assertEqual(
            result["dependency_edges"],
            [
                {
                    "source": "bips:1",
                    "target": "bips:2",
                    "extraction_method": "body_extracted_regex",
                    "relation_type": "reference",
                    "value": 1,
                }
            ],
        )

    def test_dependency_edges_use_source_safe_graph_keys(self):
        source_context = SourceContext.from_config(
            {"classification": {"dimensions": {}}},
            source_slug="bips",
        )
        result = build_network_data(
            [_proposal("1", regex_refs=["BIP 2"], requires=["BIP 2"]), _proposal("2")],
            id_field="bip",
            proposal_label="BIP",
            source_context=source_context,
        )

        self.assertEqual(result["nodes"][0]["graph_key"], "bips:1")
        self.assertIn(
            {
                "source": "bips:1",
                "target": "bips:2",
                "extraction_method": "body_extracted_regex",
                "relation_type": "reference",
                "value": 1,
            },
            result["dependency_edges"],
        )
        self.assertIn(
            {
                "source": "bips:1",
                "target": "bips:2",
                "extraction_method": "preamble_extracted",
                "relation_type": "requires",
                "value": 1,
            },
            result["dependency_edges"],
        )

    def test_rich_llm_dependencies_create_source_aware_edges(self):
        source_context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["bips"],
            ecosystem_slug="bitcoin",
            source_slug="bips",
        )

        result = build_network_data(
            [
                _proposal(
                    "1",
                    llm_deps=[
                        {
                            "target": "slips:132",
                        }
                    ],
                )
            ],
            id_field="bip",
            proposal_label="BIP",
            source_context=source_context,
            known_proposal_ids_by_source={"slips": {"132"}},
        )

        self.assertIn(
            {
                "source": "bips:1",
                "target": "slips:132",
                "extraction_method": "body_extracted_llm",
                "relation_type": "implicit_dependency",
                "value": 1,
            },
            result["dependency_edges"],
        )
        self.assertNotIn("links", result)

    def test_source_qualified_references_create_cross_source_edges(self):
        context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["slips"],
            ecosystem_slug="bitcoin",
            source_slug="slips",
        )
        slip_132 = {
            "raw": {"preamble": {"slip": "132", "title": "Registered HD version bytes for BIP-0032"}},
            "insights": {
                "interrelations": {
                    "body_extracted_regex": [{"target": "bips:32", "count": 1}, {"target": "slips:32", "count": 1}],
                    "body_extracted_llm": [],
                    "preamble_extracted": [],
                }
            },
        }
        slip_32 = {
            "raw": {"preamble": {"slip": "32", "title": "Extended serialization format for BIP-32 wallets"}},
            "insights": {
                "interrelations": {
                    "body_extracted_regex": [],
                    "body_extracted_llm": [],
                    "preamble_extracted": [],
                }
            },
        }

        result = build_network_data(
            [slip_132, slip_32],
            id_field="slip",
            proposal_label="SLIP",
            source_context=context,
            known_proposal_ids_by_source={"bips": {"32"}, "slips": {"32", "132"}},
        )

        self.assertIn(
            {
                "source": "slips:132",
                "target": "bips:32",
                "extraction_method": "body_extracted_regex",
                "relation_type": "reference",
                "value": 1,
            },
            result["dependency_edges"],
        )
        self.assertIn(
            {
                "source": "slips:132",
                "target": "slips:32",
                "extraction_method": "body_extracted_regex",
                "relation_type": "reference",
                "value": 1,
            },
            result["dependency_edges"],
        )

    def test_ground_truth_curated_edges_are_imported_for_matching_source(self):
        context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["bips"],
            ecosystem_slug="bitcoin",
            source_slug="bips",
        )
        result = build_network_data(
            [_proposal("44"), _proposal("32")],
            id_field="bip",
            proposal_label="BIP",
            source_context=context,
            known_proposal_ids_by_source={"bips": {"44", "32"}, "slips": {"44"}},
            ground_truth_entries=[
                {
                    "source": "bips:44",
                    "target": "bips:32",
                    "relation_type": "depends_on",
                    "confidence": "high",
                    "evidence": "Requires: 32",
                    "note": "Declared in preamble",
                    "reviewer": "rbo",
                    "reviewed_at": "2026-06-22",
                },
                {
                    "source": "slips:44",
                    "target": "bips:44",
                    "relation_type": "references",
                },
            ],
        )

        self.assertIn(
            {
                "source": "bips:44",
                "target": "bips:32",
                "extraction_method": "ground_truth_curated",
                "relation_type": "depends_on",
                "value": 1,
                "confidence": "high",
                "evidence": "Requires: 32",
                "note": "Declared in preamble",
                "reviewer": "rbo",
                "reviewed_at": "2026-06-22",
            },
            result["dependency_edges"],
        )
        self.assertEqual(
            [edge for edge in result["dependency_edges"] if edge["extraction_method"] == "ground_truth_curated"],
            [
                {
                    "source": "bips:44",
                    "target": "bips:32",
                    "extraction_method": "ground_truth_curated",
                    "relation_type": "depends_on",
                    "value": 1,
                    "confidence": "high",
                    "evidence": "Requires: 32",
                    "note": "Declared in preamble",
                    "reviewer": "rbo",
                    "reviewed_at": "2026-06-22",
                }
            ],
        )

    def test_ground_truth_csv_loader_trims_headers_and_skips_comments(self):
        rows = load_ground_truth_curated_entries("bitcoin")

        self.assertTrue(rows)
        self.assertEqual(rows[0]["reviewed_at"], "2026-06-22")
        self.assertIn("relation_type", rows[0])
        self.assertNotIn("reviewed_at ", rows[0])

    def test_ground_truth_validation_rejects_duplicates_and_unknown_sources(self):
        errors = validate_ground_truth_curated_entries(
            [
                {
                    "source": "bips:44",
                    "target": "bips:32",
                    "relation_type": "depends_on",
                    "__line__": 2,
                },
                {
                    "source": "bips:44",
                    "target": "bips:32",
                    "relation_type": "depends_on",
                    "__line__": 3,
                },
                {
                    "source": "bips:44",
                    "target": "bips:32",
                    "relation_type": "supersedes",
                    "__line__": 4,
                },
                {
                    "source": "bogus:1",
                    "target": "bips:32",
                    "relation_type": "depends_on",
                    "__line__": 5,
                },
            ],
            source_configs_by_slug={
                "bips": {
                    "source_slug": "bips",
                    "proposal_label": "BIP",
                    "reference_pattern": r"\bBIP[-#\s]?(\d+)\b",
                    "max_proposal_id": 9999,
                }
            },
        )

        error_text = "\n".join(errors)
        self.assertIn("duplicate curated edge", error_text)
        self.assertIn("conflicting relation types", error_text)
        self.assertIn("unknown source slug `bogus`", error_text)

    def test_unknown_cross_source_targets_are_excluded_when_known_ids_are_available(self):
        context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["slips"],
            ecosystem_slug="bitcoin",
            source_slug="slips",
        )
        result = build_network_data(
            [
                {
                    "raw": {"preamble": {"slip": "132", "title": "Registered HD version bytes"}},
                    "insights": {
                        "interrelations": {
                            "body_extracted_regex": [{"target": "bips:999", "count": 1}],
                            "body_extracted_llm": [],
                            "preamble_extracted": [],
                        }
                    },
                }
            ],
            id_field="slip",
            proposal_label="SLIP",
            source_context=context,
            known_proposal_ids_by_source={"bips": {"32"}, "slips": {"132"}},
        )

        self.assertEqual(result["dependency_edges"], [])

    def test_dependency_metrics_use_canonical_edges_when_present(self):
        network_data = {
            "nodes": [
                {"id": "1", "graph_key": "bips:1", "title": "Proposal 1"},
                {"id": "2", "graph_key": "bips:2", "title": "Proposal 2"},
            ],
            "dependency_edges": [
                {
                    "source": "bips:1",
                    "target": "bips:2",
                    "extraction_method": "preamble_extracted",
                    "relation_type": "requires",
                    "value": 1,
                }
            ],
        }

        metrics = extract_dependency_metrics(network_data)

        self.assertEqual(metrics["by_approach"]["preamble_extracted"]["summary"]["edge_count"], 1)
        per_bip_ids = {row["id"] for row in metrics["by_approach"]["preamble_extracted"]["per_bip"]}
        self.assertEqual(per_bip_ids, {"bips:1", "bips:2"})

    def test_dependency_metrics_preserve_duplicate_ids_across_sources(self):
        network_data = {
            "nodes": [
                {"id": "32", "graph_key": "bips:32", "title": "BIP 32"},
                {"id": "32", "graph_key": "slips:32", "title": "SLIP 32"},
                {"id": "132", "graph_key": "slips:132", "title": "SLIP 132"},
            ],
            "dependency_edges": [
                {
                    "source": "bips:32",
                    "target": "slips:132",
                    "extraction_method": "body_extracted_regex",
                    "relation_type": "reference",
                    "value": 1,
                },
                {
                    "source": "slips:32",
                    "target": "slips:132",
                    "extraction_method": "body_extracted_regex",
                    "relation_type": "reference",
                    "value": 1,
                },
            ],
        }

        metrics = extract_dependency_metrics(network_data)
        per_bip_ids = {row["id"] for row in metrics["by_approach"]["body_extracted_regex"]["per_bip"]}

        self.assertEqual(per_bip_ids, {"bips:32", "slips:32", "slips:132"})

    def test_merge_source_network_data_preserves_source_scoped_nodes_and_edges(self):
        self.assertEqual(combined_source_key(["slips", "bips"]), "bips+slips")

        merged = merge_source_network_data([
            (
                "bips",
                {
                    "nodes": [{"id": "32", "graph_key": "bips:32", "title": "BIP 32"}],
                    "dependency_edges": [
                        {
                            "source": "bips:32",
                            "target": "slips:132",
                            "extraction_method": "body_extracted_regex",
                            "relation_type": "reference",
                            "value": 1,
                        }
                    ],
                },
            ),
            (
                "slips",
                {
                    "nodes": [
                        {"id": "32", "graph_key": "slips:32", "title": "SLIP 32"},
                        {"id": "132", "graph_key": "slips:132", "title": "SLIP 132"},
                    ],
                    "dependency_edges": [],
                },
            ),
        ])

        self.assertEqual({node["graph_key"] for node in merged["nodes"]}, {"bips:32", "slips:32", "slips:132"})
        self.assertEqual(merged["meta"]["combination_key"], "bips+slips")
        self.assertEqual(merged["dependency_edges"][0]["source"], "bips:32")
        self.assertEqual(merged["dependency_edges"][0]["target"], "slips:132")

    def test_dependency_metrics_can_filter_custom_preamble_relation_type(self):
        network_data = {
            "nodes": [
                {"id": "1", "graph_key": "xips:1", "title": "Proposal 1"},
                {"id": "2", "graph_key": "xips:2", "title": "Proposal 2"},
            ],
            "dependency_edges": [
                {
                    "source": "xips:1",
                    "target": "xips:2",
                    "extraction_method": "preamble_extracted",
                    "relation_type": "depends_on",
                    "value": 1,
                }
            ],
        }

        graph = build_graph(network_data, link_type="depends_on")

        self.assertEqual(list(graph.edges()), [("xips:1", "xips:2")])

    def test_link_to_unknown_node_excluded(self):
        result = build_network_data([_proposal("1", regex_refs=["BIP 99"])],
                                    id_field="bip", proposal_label="BIP")
        self.assertEqual(result["dependency_edges"], [])

    def test_llm_link_to_unknown_node_excluded(self):
        result = build_network_data([_proposal("1", llm_deps=["BIP 99"])],
                                    id_field="bip", proposal_label="BIP")
        self.assertEqual(result["dependency_edges"], [])

    def test_duplicate_proposal_ids_deduplicated(self):
        result = build_network_data([_proposal("1"), _proposal("1")],
                                    id_field="bip", proposal_label="BIP")
        self.assertEqual(len(result["nodes"]), 1)

    def test_first_day_git_committers_drive_network_author_fallback(self):
        history = [
            ("c4", "2022-05-04T09:00:00+00:00", "Later Author"),
            ("c3", "2022-05-01T15:00:00+00:00", "First Day B"),
            ("c2", "2022-05-01T09:00:00+00:00", "First Day A"),
            ("c1", "2022-05-01T08:00:00+00:00", "GitHub"),
        ]
        proposal = {
            "raw": {"preamble": {"nip": "01", "title": "Proposal 01", "status": "Draft"}},
            "meta": {"git_history": history},
            "insights": {
                "formal_compliance": {},
                "interrelations": {
                    "body_extracted_regex": [],
                    "body_extracted_llm": [],
                    "preamble_extracted": [],
                },
            },
        }

        result = build_network_data([proposal], id_field="nip", proposal_label="NIP")

        self.assertEqual(result["nodes"][0]["author"], ["First Day B", "First Day A"])


if __name__ == "__main__":
    unittest.main()
