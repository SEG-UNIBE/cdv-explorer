import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from analysis.authorship.mining import get_git_history, update_metadata_from_git
from analysis.conformity.metrics import extract_conformity_metrics
from analysis.dependencies.network import build_network_data
from analysis.proposal_schema import (
    get_interrelations,
    is_llm_runs_format,
    latest_llm_findings,
)
from tests.helpers import proposal as _proposal


class UpdateMetadataFromGitTests(unittest.TestCase):
    def test_git_history_includes_author_email(self):
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=(
                "c2|2022-05-02T09:00:00+00:00|Alias Name|alias@example.com\n"
                "c1|2022-05-01T08:00:00+00:00|Real Name|real@example.com"
            ),
        )

        with patch("analysis.authorship.mining.subprocess.run", return_value=completed):
            history = get_git_history(
                Path("/repo"), Path("/repo/proposals/bip-0001.md")
            )

        self.assertEqual(
            history,
            [
                ("c2", "2022-05-02T09:00:00+00:00", "Alias Name", "alias@example.com"),
                ("c1", "2022-05-01T08:00:00+00:00", "Real Name", "real@example.com"),
            ],
        )

    def test_backfills_authors_from_first_day_committers_only(self):
        history = [
            ("c4", "2022-05-04T09:00:00+00:00", "Later Author", "later@example.com"),
            ("c3", "2022-05-01T15:00:00+00:00", "First Day B", "b@example.com"),
            ("c2", "2022-05-01T09:00:00+00:00", "First Day A", "a@example.com"),
            ("c1", "2022-05-01T08:00:00+00:00", "GitHub", "noreply@github.com"),
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

        self.assertEqual(
            updated["raw"]["preamble"]["author"], ["First Day B", "First Day A"]
        )
        self.assertEqual(updated["raw"]["preamble"]["created"], "2022-05-01")


class ExtractConformityMetricsTests(unittest.TestCase):
    def test_empty_input_returns_empty_structures(self):
        result = extract_conformity_metrics([], id_field="bip")
        self.assertEqual(result["per_proposal"], [])
        self.assertEqual(result["average_score_by_standard"], {})
        self.assertEqual(result["check_summary"], [])

    def test_averages_scores_by_standard(self):
        proposals = [
            _proposal("1", bip2_score=80.0, bip3_score=60.0),
            _proposal("2", bip2_score=60.0, bip3_score=40.0),
        ]
        result = extract_conformity_metrics(proposals, id_field="bip")
        self.assertEqual(result["average_score_by_standard"]["bip2"], 70.0)
        self.assertEqual(result["average_score_by_standard"]["bip3"], 50.0)

    def test_check_summary_aggregates_pass_and_fail_counts(self):
        check = {
            "id": "c1",
            "label": "Has title",
            "category": "required_field",
            "standard": "bip2",
        }
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
        runs = [
            {
                "model": "gpt-5",
                "timestamp": "2026-06-11T10:00:00Z",
                "status": "success",
                "findings": [],
            }
        ]
        self.assertTrue(is_llm_runs_format(runs))

    def test_does_not_detect_old_flat_format_as_runs(self):
        self.assertFalse(is_llm_runs_format(["BIP 32"]))
        self.assertFalse(is_llm_runs_format([{"target": "bips:32"}]))
        self.assertFalse(
            is_llm_runs_format(
                [
                    {
                        "model": "gpt-5",
                        "timestamp": "2026-06-11T10:00:00Z",
                        "findings": [],
                    }
                ]
            )
        )
        self.assertFalse(is_llm_runs_format([]))

    def test_rejects_mixed_llm_run_shape(self):
        self.assertFalse(
            is_llm_runs_format(
                [
                    {
                        "model": "gpt-5",
                        "timestamp": "2026-06-11T10:00:00Z",
                        "status": "success",
                        "findings": [],
                    },
                    {
                        "model": "gpt-5",
                        "timestamp": "2026-06-12T10:00:00Z",
                        "findings": [],
                    },
                ]
            )
        )

    def test_latest_run_findings_are_returned(self):
        runs = [
            {
                "model": "gpt-4",
                "timestamp": "2026-01-01T00:00:00Z",
                "status": "success",
                "findings": [{"target": "bips:1"}],
            },
            {
                "model": "gpt-5",
                "timestamp": "2026-06-01T00:00:00Z",
                "status": "success",
                "findings": [{"target": "bips:32"}],
            },
        ]
        self.assertEqual(latest_llm_findings(runs), [{"target": "bips:32"}])

    def test_latest_run_is_selected_by_timestamp_not_position(self):
        runs = [
            {
                "model": "gpt-5",
                "timestamp": "2026-06-01T00:00:00Z",
                "status": "success",
                "findings": [{"target": "bips:32"}],
            },
            {
                "model": "gpt-4",
                "timestamp": "2026-01-01T00:00:00Z",
                "status": "success",
                "findings": [{"target": "bips:1"}],
            },
        ]
        self.assertEqual(latest_llm_findings(runs), [{"target": "bips:32"}])

    def test_old_flat_format_is_ignored(self):
        flat = [{"target": "bips:32"}]
        self.assertEqual(latest_llm_findings(flat), [])

    def test_get_interrelations_resolves_latest_run(self):
        runs = [
            {
                "model": "gpt-4",
                "timestamp": "2026-01-01T00:00:00Z",
                "status": "success",
                "findings": [{"target": "bips:1"}],
            },
            {
                "model": "gpt-5",
                "timestamp": "2026-06-01T00:00:00Z",
                "status": "success",
                "findings": [{"target": "bips:32"}],
            },
        ]
        result = get_interrelations(self._proposal_with_runs(runs))
        self.assertEqual(result["body_extracted_llm"], [{"target": "bips:32"}])

    def test_network_data_uses_latest_llm_run(self):
        runs = [
            {
                "model": "gpt-4",
                "timestamp": "2026-01-01T00:00:00Z",
                "status": "success",
                "findings": [{"target": "bips:99", "type": "depends_on"}],
            },
            {
                "model": "gpt-5",
                "timestamp": "2026-06-01T00:00:00Z",
                "status": "success",
                "findings": [{"target": "bips:2", "type": "depends_on"}],
            },
        ]
        proposals = [
            self._proposal_with_runs(runs),
            {
                "raw": {"preamble": {"bip": "2", "title": "P2"}},
                "insights": {
                    "interrelations": {
                        "preamble_extracted": [],
                        "body_extracted_regex": [],
                        "body_extracted_llm": [],
                    }
                },
            },
        ]

        result = build_network_data(
            proposals,
            id_field="bip",
            proposal_label="BIP",
            ground_truth_entries=[],
            reviewed_ips_entries=[],
        )

        self.assertEqual(
            result["dependency_edges"],
            [
                {
                    "source": "bips:1",
                    "target": "bips:2",
                    "extraction_method": "body_extracted_llm",
                    "relation_type": "depends_on",
                    "value": 1,
                    "llm_model": "gpt-5",
                    "evidence": None,
                    "reason": None,
                    "confidence": None,
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
