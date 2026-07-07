from unittest import TestCase

from analysis.pipeline import _trim_conformity_checks


class TestTrimConformityChecks(TestCase):
    def test_keeps_only_failed_checks_with_rendered_fields(self):
        metrics = {
            "check_summary": [{"id": "bip2.b", "failures": 1}],
            "per_proposal": [
                {
                    "id": "1",
                    "status": "Final",
                    "standard_scores": {"bip2": 50.0},
                    "formal_compliance": {
                        "score": 50.0,
                        "passed_checks": 1,
                        "failed_checks": 1,
                        "bip2": {
                            "score": 50.0,
                            "passed_checks": 1,
                            "failed_checks": 1,
                            "skipped_checks": 0,
                            "total_checks": 2,
                            "checks": [
                                {
                                    "id": "bip2.a",
                                    "label": "A",
                                    "category": "required_field",
                                    "standard": "bip2",
                                    "passed": True,
                                    "details": None,
                                },
                                {
                                    "id": "bip2.b",
                                    "label": "B",
                                    "category": "required_field",
                                    "standard": "bip2",
                                    "passed": False,
                                    "details": "missing",
                                },
                            ],
                        },
                    },
                }
            ],
        }

        trimmed = _trim_conformity_checks(metrics)

        row = trimmed["per_proposal"][0]
        self.assertEqual(
            row["formal_compliance"]["bip2"]["checks"],
            [{"id": "bip2.b", "label": "B", "passed": False, "details": "missing"}],
        )
        # Aggregate counters and summary sections survive untrimmed.
        self.assertEqual(row["formal_compliance"]["bip2"]["failed_checks"], 1)
        self.assertEqual(row["formal_compliance"]["bip2"]["total_checks"], 2)
        self.assertEqual(trimmed["check_summary"], metrics["check_summary"])
        # The input payload is not mutated (Stage III artifacts share it).
        original_checks = metrics["per_proposal"][0]["formal_compliance"]["bip2"]["checks"]
        self.assertEqual(len(original_checks), 2)
        self.assertIn("category", original_checks[0])

    def test_handles_combined_placeholder_payloads(self):
        placeholder = {"meta": {"merge_status": "not_mergeable"}, "per_proposal": []}
        self.assertEqual(_trim_conformity_checks(placeholder)["per_proposal"], [])
