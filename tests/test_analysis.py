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
    create_explicit_dependency_targets,
    create_reference_list,
    create_reference_targets,
    llm_extract_implicit_dependencies,
    normalize_dependency_output,
    normalize_llm_dependency_output,
    prepare_llm_dependency_text,
)
from analysis.dependencies.metrics import build_graph, extract_dependency_metrics
from analysis.dependencies.network import build_network_data
from analysis.dependencies.utils import uses_hex_proposal_ids
from analysis.proposal_schema import get_interrelations, is_llm_runs_format, latest_llm_dependencies
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

    def target_entries(value):
        if value is None:
            return []
        values = value if isinstance(value, list) else [value]
        return [{"target": ref} for ref in values]

    return {
        "raw": {"preamble": preamble},
        "insights": {
            "formal_compliance": compliance,
            "interrelations": {
                "body_extracted_regex": regex_refs or [],
                "body_extracted_llm": llm_deps or [],
                "preamble_extracted": [
                    {**entry, "type": "requires"} for entry in target_entries(requires)
                ] + [
                    {**entry, "type": "replaces"} for entry in target_entries(replaces)
                ] + [
                    {**entry, "type": "proposed_replacement"} for entry in target_entries(proposed_replacement)
                ],
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

    def test_detects_hex_ids_from_reference_pattern_for_non_nip_sources(self):
        context = SourceContext.from_config(
            {
                "proposal_acronym": "XIP",
                "proposal_term_singular": "Example Improvement Proposal",
                "reference_pattern": r"\bXIP-([0-9A-Fa-f]{1,3})\b",
            },
            source_slug="xips",
        )

        result = create_reference_list(
            "This builds on XIP-0A and XIP-10.",
            proposal_label="XIP",
            reference_pattern=r"\bXIP-([0-9A-Fa-f]{1,3})\b",
            source_context=context,
        )

        self.assertEqual(result, ["XIP 0A", "XIP 10"])

    def test_hex_detection_requires_hex_character_class(self):
        self.assertFalse(uses_hex_proposal_ids("BIP", r"\bBCA-FLAG-(\d+)\b"))
        self.assertTrue(uses_hex_proposal_ids("XIP", r"\bXIP-([0-9A-Fa-f]{1,3})\b"))

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


class CreateReferenceTargetsTests(unittest.TestCase):
    def test_counts_repeated_regex_references_by_target(self):
        context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["bips"],
            ecosystem_slug="bitcoin",
            source_slug="bips",
        )

        result = create_reference_targets(
            "BIP 32 references BIP-32 and BIPs 32 and 39.",
            proposal_label="BIP",
            reference_pattern=r"\bBIP[-#\s]?(\d+)\b",
            source_context=context,
        )

        self.assertEqual(
            result,
            [{"target": "bips:32", "count": 3}, {"target": "bips:39", "count": 1}],
        )

    def test_counts_mixed_bip_reference_syntax_variants(self):
        context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["bips"],
            ecosystem_slug="bitcoin",
            source_slug="bips",
        )

        result = create_reference_targets(
            """
            This proposal cites BIP 32, BIP-32, BIP #32, BIP - 32, and BIP32.
            It also references BIPs 33 and 99, BIPs 33/99, and bip-99.
            It points implementers to SLIP-0132 for registered version bytes.
            BIP 1000 is outside the configured BIP range and should be ignored.
            """,
            proposal_label="BIP",
            reference_pattern=r"\bBIP[-#\s]?(\d+)\b",
            source_context=context,
        )

        self.assertEqual(
            result,
            [
                {"target": "bips:32", "count": 5},
                {"target": "bips:33", "count": 2},
                {"target": "bips:99", "count": 3},
                {"target": "slips:132", "count": 1},
            ],
        )

    def test_detects_sibling_source_targets(self):
        context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["slips"],
            ecosystem_slug="bitcoin",
            source_slug="slips",
        )

        result = create_reference_targets(
            "SLIP-0132 registers version bytes for BIP-0032 and BIPs 39 and 44.",
            proposal_label="SLIP",
            reference_pattern=r"\bSLIP[-#\s]?(\d+)\b",
            source_context=context,
        )

        self.assertEqual(
            result,
            [
                {"target": "bips:32", "count": 1},
                {"target": "bips:39", "count": 1},
                {"target": "bips:44", "count": 1},
                {"target": "slips:132", "count": 1},
            ],
        )


class CreateExplicitDependencyTargetsTests(unittest.TestCase):
    def test_keeps_preamble_dependency_subtypes(self):
        context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["bips"],
            ecosystem_slug="bitcoin",
            source_slug="bips",
        )

        result = create_explicit_dependency_targets(
            {"requires": "BIP 32, SLIP-0132", "replaces": "1"},
            proposal_label="BIP",
            source_context=context,
        )

        self.assertEqual(
            result,
            [
                {"target": "bips:32", "type": "requires"},
                {"target": "slips:132", "type": "requires"},
                {"target": "bips:1", "type": "replaces"},
            ],
        )

    def test_uses_source_configured_preamble_interrelation_types(self):
        context = SourceContext.from_config(
            {
                "proposal_acronym": "XIP",
                "reference_pattern": r"\bXIP[-#\s]?(\d+)\b",
                "preamble": {"interrelation_types": ["depends_on"]},
            },
            source_slug="xips",
        )

        result = create_explicit_dependency_targets(
            {"depends_on": "XIP 7", "requires": "XIP 8"},
            proposal_label="XIP",
            source_context=context,
        )

        self.assertEqual(result, [{"target": "xips:7", "type": "depends_on"}])


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


class LlmModelConfigTests(unittest.TestCase):
    def test_llm_extraction_requires_configured_model(self):
        context = SourceContext.from_config(
            {
                "proposal_acronym": "BIP",
                "proposal_term_singular": "Bitcoin Improvement Proposal",
                "reference_pattern": r"\bBIP[-#\s]?(\d+)\b",
            }
        )

        with self.assertRaisesRegex(RuntimeError, "No LLM model configured"):
            llm_extract_implicit_dependencies(
                "This proposal depends on BIP 32.",
                api_key="test-key",
                source_context=context,
            )

    def test_llm_fallback_json_errors_are_wrapped(self):
        context = SourceContext.from_config(
            {
                "proposal_acronym": "BIP",
                "proposal_term_singular": "Bitcoin Improvement Proposal",
                "reference_pattern": r"\bBIP[-#\s]?(\d+)\b",
            },
            source_slug="bips",
        )

        def create_completion(**kwargs):
            if kwargs["response_format"]["type"] == "json_schema":
                raise TypeError("structured outputs unsupported")
            message = types.SimpleNamespace(content="{not json", refusal=None)
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

        client = types.SimpleNamespace(
            chat=types.SimpleNamespace(
                completions=types.SimpleNamespace(create=create_completion)
            )
        )

        with patch("analysis.dependencies.mining.OpenAI", return_value=client):
            with self.assertRaisesRegex(RuntimeError, "LLM API call failed"):
                llm_extract_implicit_dependencies(
                    "This proposal depends on BIP 32.",
                    api_key="test-key",
                    model="test-model",
                    source_context=context,
                )


class NormalizeLlmDependencyOutputTests(unittest.TestCase):
    def test_returns_rich_source_aware_dependency_objects(self):
        context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["bips"],
            ecosystem_slug="bitcoin",
            source_slug="bips",
        )

        result = normalize_llm_dependency_output(
            [
                {
                    "target": "BIP 32",
                    "evidence": "depends on BIP 32",
                    "reason": "It relies on hierarchical deterministic wallets.",
                    "confidence": "HIGH",
                },
                {
                    "target": "slips:132",
                    "evidence": "uses SLIP-0132 version bytes",
                    "reason": "It relies on version byte definitions from SLIP 132.",
                    "confidence": "medium",
                },
            ],
            proposal_label="BIP",
            current_proposal_number="1",
            source_context=context,
        )

        self.assertEqual(
            result,
            [
                {
                    "target": "bips:32",
                    "evidence": "depends on BIP 32",
                    "reason": "It relies on hierarchical deterministic wallets.",
                    "confidence": "high",
                },
                {
                    "target": "slips:132",
                    "evidence": "uses SLIP-0132 version bytes",
                    "reason": "It relies on version byte definitions from SLIP 132.",
                    "confidence": "medium",
                },
            ],
        )
        self.assertTrue(all("_label" not in entry for entry in result))

    def test_excludes_current_proposal_and_deduplicates_targets(self):
        context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["bips"],
            ecosystem_slug="bitcoin",
            source_slug="bips",
        )

        result = normalize_llm_dependency_output(
            [
                {"target": "bips:32", "evidence": "self", "reason": "self", "confidence": "high"},
                {"target": "BIP-39", "evidence": "first", "reason": "first", "confidence": "unexpected"},
                {"target": "bips:39", "evidence": "second", "reason": "second", "confidence": "high"},
            ],
            proposal_label="BIP",
            current_proposal_number="32",
            source_context=context,
        )

        self.assertEqual(
            result,
            [{"target": "bips:39", "evidence": "first", "reason": "first", "confidence": "low"}],
        )


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
                            "evidence": "uses SLIP-0132 version bytes",
                            "reason": "It relies on version byte definitions.",
                            "confidence": "high",
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


class LlmRunsFormatTests(unittest.TestCase):
    def _proposal_with_runs(self, runs):
        return {
            "raw": {"preamble": {"bip": "1"}},
            "insights": {
                "interrelations": {
                    "preamble_extracted": [],
                    "body_extracted_regex": [],
                    "body_extracted_llm": runs,
                }
            },
        }

    def test_detects_new_runs_format(self):
        runs = [{"model": "gpt-5", "timestamp": "2026-06-11T10:00:00Z", "dependencies": []}]
        self.assertTrue(is_llm_runs_format(runs))

    def test_does_not_detect_old_flat_format_as_runs(self):
        self.assertFalse(is_llm_runs_format(["BIP 32"]))
        self.assertFalse(is_llm_runs_format([{"target": "bips:32", "confidence": "high"}]))
        self.assertFalse(is_llm_runs_format([]))

    def test_latest_run_dependencies_are_returned(self):
        runs = [
            {"model": "gpt-4", "timestamp": "2026-01-01T00:00:00Z", "dependencies": [{"target": "bips:1"}]},
            {"model": "gpt-5", "timestamp": "2026-06-01T00:00:00Z", "dependencies": [{"target": "bips:32"}]},
        ]
        self.assertEqual(latest_llm_dependencies(runs), [{"target": "bips:32"}])

    def test_latest_run_is_selected_by_timestamp_not_position(self):
        runs = [
            {"model": "gpt-5", "timestamp": "2026-06-01T00:00:00Z", "dependencies": [{"target": "bips:32"}]},
            {"model": "gpt-4", "timestamp": "2026-01-01T00:00:00Z", "dependencies": [{"target": "bips:1"}]},
        ]
        self.assertEqual(latest_llm_dependencies(runs), [{"target": "bips:32"}])

    def test_old_flat_format_passed_through_unchanged(self):
        flat = [{"target": "bips:32", "evidence": "x", "reason": "y", "confidence": "high"}]
        self.assertEqual(latest_llm_dependencies(flat), flat)

    def test_get_interrelations_resolves_latest_run(self):
        runs = [
            {"model": "gpt-4", "timestamp": "2026-01-01T00:00:00Z", "dependencies": [{"target": "bips:1"}]},
            {"model": "gpt-5", "timestamp": "2026-06-01T00:00:00Z", "dependencies": [{"target": "bips:32"}]},
        ]
        result = get_interrelations(self._proposal_with_runs(runs))
        self.assertEqual(result["body_extracted_llm"], [{"target": "bips:32"}])

    def test_network_data_uses_latest_llm_run(self):
        runs = [
            {"model": "gpt-4", "timestamp": "2026-01-01T00:00:00Z", "dependencies": [{"target": "bips:99", "evidence": "", "reason": "", "confidence": "low"}]},
            {"model": "gpt-5", "timestamp": "2026-06-01T00:00:00Z", "dependencies": [{"target": "bips:2", "evidence": "x", "reason": "y", "confidence": "high"}]},
        ]
        proposals = [
            self._proposal_with_runs(runs),
            {"raw": {"preamble": {"bip": "2", "title": "P2"}}, "insights": {"interrelations": {"preamble_extracted": [], "body_extracted_regex": [], "body_extracted_llm": []}}},
        ]
        result = build_network_data(proposals, id_field="bip", proposal_label="BIP")
        targets = {e["target"] for e in result["dependency_edges"]}
        self.assertIn("bips:2", targets)
        self.assertNotIn("bips:99", targets)


if __name__ == "__main__":
    unittest.main()
