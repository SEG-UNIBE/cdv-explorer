import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

if "openai" not in sys.modules:
    fake_openai = types.ModuleType("openai")
    fake_openai.OpenAI = type("OpenAI", (), {})
    sys.modules["openai"] = fake_openai

from analysis.conformity.metrics import extract_conformity_metrics
from analysis.authorship.mining import update_metadata_from_git
from analysis.dependencies.mining import (
    create_reference_list,
    normalize_dependency_output,
    prepare_llm_dependency_text,
)
from analysis.dependencies.metrics import extract_dependency_metrics
from analysis.dependencies.network import build_network_data
from ecosystems import ECOSYSTEM_REGISTRY
from pipeline.source_context import SourceContext


def _proposal(
    bip_id,
    *,
    regex_refs=None,
    llm_deps=None,
    requires=None,
    replaces=None,
    proposed_replacement=None,
    status="Draft",
    bip2_score=None,
    bip3_score=None,
    checks=None,
):
    compliance = {}
    if bip2_score is not None:
        compliance["bip2"] = {"score": bip2_score, "checks": checks or []}
    if bip3_score is not None:
        compliance["bip3"] = {"score": bip3_score, "checks": []}
    if compliance:
        compliance["score"] = bip2_score
    preamble = {"bip": bip_id, "title": f"Proposal {bip_id}", "status": status}
    if requires is not None:
        preamble["requires"] = requires
    if replaces is not None:
        preamble["replaces"] = replaces
    if proposed_replacement is not None:
        preamble["proposed_replacement"] = proposed_replacement
    return {
        "raw": {"preamble": preamble},
        "insights": {
            "formal_compliance": compliance,
            "interrelations": {
                "body_extracted_regex": regex_refs or [],
                "body_extracted_llm": llm_deps or [],
                "preamble_extracted": [],
            },
        },
    }


class NormalizeDependencyOutputTests(unittest.TestCase):
    def test_recognizes_various_formats_as_same_id(self):
        result = normalize_dependency_output(["BIP 32", "BIP-32", "BIP-0032", "32"], proposal_label="BIP")
        self.assertEqual(result, ["BIP 32"])

    def test_excludes_current_proposal(self):
        result = normalize_dependency_output(["BIP 32", "BIP 39"], proposal_label="BIP", current_proposal_number="32")
        self.assertEqual(result, ["BIP 39"])

    def test_non_list_input_returns_empty(self):
        self.assertEqual(normalize_dependency_output("BIP 32", proposal_label="BIP"), [])
        self.assertEqual(normalize_dependency_output(None, proposal_label="BIP"), [])

    def test_garbled_items_are_skipped(self):
        result = normalize_dependency_output(["BIP 32", "not a bip", "", "BIP 39"], proposal_label="BIP")
        self.assertEqual(result, ["BIP 32", "BIP 39"])

    def test_output_is_sorted_numerically(self):
        result = normalize_dependency_output(["BIP 200", "BIP 1", "BIP 50"], proposal_label="BIP")
        self.assertEqual(result, ["BIP 1", "BIP 50", "BIP 200"])

    def test_ids_exceeding_ecosystem_max_are_excluded(self):
        result = normalize_dependency_output(["BIP 999", "BIP 1000"], proposal_label="BIP")
        self.assertEqual(result, ["BIP 999"])

    def test_hex_nip_ids_preserve_width_and_exclude_current_proposal(self):
        result = normalize_dependency_output(
            ["NIP 1", "NIP-01", "NIP F4"],
            proposal_label="NIP",
            current_proposal_number="F4",
        )
        self.assertEqual(result, ["NIP 01"])


class CreateReferenceListTests(unittest.TestCase):
    def test_detects_single_inline_reference(self):
        result = create_reference_list("This builds on BIP 32 for key derivation.")
        self.assertIn("BIP 32", result)

    def test_detects_comma_separated_list_syntax(self):
        result = create_reference_list("See BIPs 32 and 39 for details.")
        self.assertIn("BIP 32", result)
        self.assertIn("BIP 39", result)

    def test_empty_text_returns_empty(self):
        self.assertEqual(create_reference_list(""), [])

    def test_text_without_references_returns_empty(self):
        self.assertEqual(create_reference_list("no proposals mentioned here"), [])

    def test_output_is_sorted_numerically(self):
        result = create_reference_list("BIP 100 and BIP 5 are relevant.")
        self.assertLess(result.index("BIP 5"), result.index("BIP 100"))

    def test_detects_hex_nip_references(self):
        result = create_reference_list(
            "This builds on NIP-01 and NIP-F4.",
            proposal_label="NIP",
            reference_pattern=r"\bNIP-([0-9A-Fa-f]{1,3})\b",
        )
        self.assertEqual(result, ["NIP 01", "NIP F4"])

    def test_detects_sibling_source_references_from_context(self):
        context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["slips"],
            ecosystem_slug="bitcoin",
            source_slug="slips",
        )

        result = create_reference_list(
            "SLIP-0132 registers version bytes for BIP-0032 and BIPs 39 and 44.",
            proposal_label="SLIP",
            reference_pattern=r"\bSLIP[-#\s]?(\d+)\b",
            source_context=context,
        )

        self.assertEqual(result, ["BIP 32", "BIP 39", "BIP 44", "SLIP 132"])


class PrepareLlmDependencyTextTests(unittest.TestCase):
    def test_strips_leading_pre_block(self):
        raw = "<pre>\nBIP: 1\nTitle: Test\n</pre>\nThis is the body."
        result = prepare_llm_dependency_text(raw)
        self.assertNotIn("<pre>", result)
        self.assertIn("This is the body.", result)

    def test_strips_leading_fenced_code_block(self):
        raw = "```\nBIP: 1\nTitle: Test\n```\nThis is the body."
        result = prepare_llm_dependency_text(raw)
        self.assertNotIn("```", result)
        self.assertIn("This is the body.", result)

    def test_empty_input_returns_empty(self):
        self.assertEqual(prepare_llm_dependency_text(""), "")

    def test_content_without_preamble_block_is_unchanged(self):
        text = "Just plain content with no preamble block."
        self.assertEqual(prepare_llm_dependency_text(text), text)


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
                    "body_extracted_regex": ["BIP 32", "SLIP 32"],
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
                            "body_extracted_regex": ["BIP 999"],
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


class UpdateMetadataFromGitTests(unittest.TestCase):
    def test_backfills_authors_from_first_day_committers_only(self):
        history = [
            ("c4", "2022-05-04T09:00:00+00:00", "Later Author"),
            ("c3", "2022-05-01T15:00:00+00:00", "First Day B"),
            ("c2", "2022-05-01T09:00:00+00:00", "First Day A"),
            ("c1", "2022-05-01T08:00:00+00:00", "GitHub"),
        ]
        document = {
            "raw": {
                "preamble": {
                    "nip": "01",
                    "title": "Proposal 01",
                    "status": "Draft",
                }
            }
        }

        with patch("analysis.authorship.mining.get_git_history", return_value=history):
            updated = update_metadata_from_git(document, Path("01.md"), Path("."))

        self.assertEqual(updated["raw"]["preamble"]["author"], ["First Day B", "First Day A"])
        self.assertEqual(updated["raw"]["preamble"]["created"], "2022-05-01")


class ExtractConformityMetricsTests(unittest.TestCase):
    def test_empty_input_returns_empty_structures(self):
        result = extract_conformity_metrics([], id_field="bip")
        self.assertEqual(result["per_proposal"], [])
        self.assertEqual(result["average_score_by_standard"], {})
        self.assertEqual(result["check_summary"], [])

    def test_averages_scores_by_standard(self):
        proposals = [_proposal("1", bip2_score=80.0, bip3_score=60.0),
                     _proposal("2", bip2_score=60.0, bip3_score=40.0)]
        result = extract_conformity_metrics(proposals, id_field="bip")
        self.assertEqual(result["average_score_by_standard"]["bip2"], 70.0)
        self.assertEqual(result["average_score_by_standard"]["bip3"], 50.0)

    def test_check_summary_aggregates_pass_and_fail_counts(self):
        check = {"id": "c1", "label": "Has title", "category": "required_field", "standard": "bip2"}
        proposals = [
            _proposal("1", bip2_score=90.0, checks=[{**check, "passed": True}]),
            _proposal("2", bip2_score=50.0, checks=[{**check, "passed": False}]),
            _proposal("3", bip2_score=80.0, checks=[{**check, "passed": True}]),
        ]
        result = extract_conformity_metrics(proposals, id_field="bip")
        summary = next(c for c in result["check_summary"] if c["id"] == "c1")
        self.assertEqual(summary["pass_count"], 2)
        self.assertEqual(summary["fail_count"], 1)
        self.assertEqual(summary["pass_rate"], 66.67)

    def test_proposal_without_id_is_skipped(self):
        no_id = {"raw": {"preamble": {}}, "insights": {"formal_compliance": {}}}
        result = extract_conformity_metrics([no_id], id_field="bip")
        self.assertEqual(result["per_proposal"], [])


if __name__ == "__main__":
    unittest.main()
