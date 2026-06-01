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
from analysis.dependencies.network import build_network_data


def _proposal(bip_id, *, regex_refs=None, llm_deps=None, status="Draft", bip2_score=None, bip3_score=None, checks=None):
    compliance = {}
    if bip2_score is not None:
        compliance["bip2"] = {"score": bip2_score, "checks": checks or []}
    if bip3_score is not None:
        compliance["bip3"] = {"score": bip3_score, "checks": []}
    if compliance:
        compliance["score"] = bip2_score
    return {
        "raw": {"preamble": {"bip": bip_id, "title": f"Proposal {bip_id}", "status": status}},
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
        links = result["links"]["body_extracted_regex"]
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["source"], "1")
        self.assertEqual(links[0]["target"], "2")

    def test_link_to_unknown_node_excluded(self):
        result = build_network_data([_proposal("1", regex_refs=["BIP 99"])],
                                    id_field="bip", proposal_label="BIP")
        self.assertEqual(result["links"]["body_extracted_regex"], [])

    def test_llm_link_to_unknown_node_excluded(self):
        result = build_network_data([_proposal("1", llm_deps=["BIP 99"])],
                                    id_field="bip", proposal_label="BIP")
        self.assertEqual(result["links"]["body_extracted_llm"], [])

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
