import json
import os
import tempfile
import unittest
from pathlib import Path

from analysis.validation.ground_truth import export_ground_truth_workbook
from analysis.validation.snapshots import (
    expected_combined_snapshot_targets,
    validate_ground_truth_curated_file,
    validate_ground_truth_ips_file,
    validate_payload_index,
    validate_payload_snapshot,
    validate_preprocess_snapshot,
    validate_react_generated_indexes,
)


class SnapshotValidationTests(unittest.TestCase):
    def _source_config(self, root: Path, slug: str = "bips") -> dict:
        acronym = "BIP" if slug == "bips" else "SLIP"
        return {
            "proposal_acronym": acronym,
            "primary_id_field": slug[:-1],
            "reference_pattern": rf"\b{acronym}[-#\s]?(\d+)\b",
            "max_proposal_id": 9999,
            "preprocess": str(root / slug / "02_preprocess"),
            "analysis": str(root / slug / "03_analysis"),
            "postprocess": str(root / slug / "04_postprocess"),
            "preamble": {
                "interrelation_types": ["requires", "replaces"],
            },
        }

    def test_preprocess_validation_rejects_malformed_interrelations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            bips = self._source_config(root, "bips")
            slips = self._source_config(root, "slips")
            preprocess_dir = Path(bips["preprocess"]) / "2026-05-28"
            preprocess_dir.mkdir(parents=True)
            (preprocess_dir / "bip-0001.json").write_text(
                json.dumps(
                    {
                        "raw": {"preamble": {"bip": "1"}},
                        "meta": {
                            "git_history": [
                                [
                                    "abc",
                                    "2026-05-28T10:00:00+00:00",
                                    "Author",
                                    "author@example.com",
                                ]
                            ]
                        },
                        "insights": {
                            "interrelations": {
                                "preamble_extracted": [
                                    {"target": "bips:32", "type": "requires"},
                                    {"type": "requires"},
                                    {"target": "unknown:1", "type": "requires"},
                                    {"target": "bips:33", "type": "blocks"},
                                ],
                                "body_extracted_regex": [
                                    {"target": "bips:34", "count": 2},
                                    {"target": "bips:35"},
                                ],
                                "body_extracted_llm": [
                                    {
                                        "run_id": "run-1",
                                        "model": "gpt-test",
                                        "status": "success",
                                        "findings": [
                                            {
                                                "target": "slips:39",
                                                "type": "depends_on",
                                            },
                                            {"target": "BIP 32", "type": "depends_on"},
                                        ],
                                    }
                                ],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = validate_preprocess_snapshot(
                preprocess_dir,
                ecosystem_slug="bitcoin",
                source_slug="bips",
                source_config=bips,
                ecosystem_config={"sources": {"bips": bips, "slips": slips}},
            )

        self.assertFalse(result.ok)
        error_text = "\n".join(result.errors)
        self.assertIn("missing `target`", error_text)
        self.assertIn("unknown source slug `unknown`", error_text)
        self.assertIn("unknown relation type `blocks`", error_text)
        self.assertIn("missing positive integer `count`", error_text)
        self.assertIn("missing non-empty `timestamp`", error_text)
        self.assertIn("must use source_slug:id format", error_text)

    def test_preprocess_validation_rejects_malformed_git_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            bips = self._source_config(root, "bips")
            preprocess_dir = Path(bips["preprocess"]) / "2026-05-28"
            preprocess_dir.mkdir(parents=True)
            (preprocess_dir / "bip-0001.json").write_text(
                json.dumps(
                    {
                        "raw": {"preamble": {"bip": "1"}},
                        "meta": {
                            "git_history": [
                                ["abc", "2026-05-28T10:00:00+00:00", "Author"],
                                [
                                    "def",
                                    "2026-05-29T10:00:00+00:00",
                                    "Other Author",
                                    "",
                                ],
                                [
                                    "",
                                    "2026-05-30T10:00:00+00:00",
                                    "Third Author",
                                    "third@example.com",
                                ],
                            ]
                        },
                        "insights": {
                            "interrelations": {
                                "preamble_extracted": [],
                                "body_extracted_regex": [],
                                "body_extracted_llm": [],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = validate_preprocess_snapshot(
                preprocess_dir,
                ecosystem_slug="bitcoin",
                source_slug="bips",
                source_config=bips,
                ecosystem_config={"sources": {"bips": bips}},
            )

        self.assertFalse(result.ok)
        error_text = "\n".join(result.errors)
        self.assertIn("commit must be non-empty", error_text)
        self.assertIn("missing author_email", "\n".join(result.warnings))

    def test_payload_index_validation_rejects_missing_index_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            payload_dir = Path(tmp_dir) / "2026-05-28"
            payload_dir.mkdir()
            (payload_dir / "dataset_index.json").write_text(
                json.dumps(
                    {"files": {"network_data": "dependencies/network_data.json"}}
                ),
                encoding="utf-8",
            )

            result = validate_payload_index(payload_dir)

        self.assertFalse(result.ok)
        self.assertIn("references missing files", "\n".join(result.errors))

    def test_payload_validation_rejects_missing_contributor_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            payload_dir = Path(tmp_dir) / "2026-05-28"
            (payload_dir / "dependencies").mkdir(parents=True)
            (payload_dir / "authorship").mkdir()
            (payload_dir / "classification").mkdir()
            (payload_dir / "evolution").mkdir()
            (payload_dir / "conformity").mkdir()

            (payload_dir / "dependencies" / "network_data.json").write_text(
                json.dumps({"nodes": [{"id": "1"}], "dependency_edges": []}),
                encoding="utf-8",
            )
            (payload_dir / "dependencies" / "dependency_metrics.json").write_text(
                json.dumps(
                    {
                        "by_approach": {},
                        "pairwise_comparisons": {},
                        "pairwise_comparisons_exact_type": {},
                    }
                ),
                encoding="utf-8",
            )
            (payload_dir / "authorship" / "authorship_payload.json").write_text(
                json.dumps(
                    {
                        "meta": {},
                        "top_authors": [],
                        "bips_per_year": [],
                        "top_10_share": {},
                    }
                ),
                encoding="utf-8",
            )
            (payload_dir / "classification" / "classification_payload.json").write_text(
                json.dumps(
                    {
                        "meta": {},
                        "sankey_grouped": {},
                        "status_over_time": {},
                    }
                ),
                encoding="utf-8",
            )
            (payload_dir / "evolution" / "evolution_payload.json").write_text(
                json.dumps(
                    {
                        "meta": {},
                        "status_evolution": {},
                        "proposal_timelines": [],
                    }
                ),
                encoding="utf-8",
            )
            (payload_dir / "conformity" / "conformity_metrics.json").write_text(
                json.dumps({"per_proposal": []}),
                encoding="utf-8",
            )

            result = validate_payload_snapshot(payload_dir)

        self.assertFalse(result.ok)
        error_text = "\n".join(result.errors)
        self.assertIn("node `1` missing `contributors` list", error_text)
        self.assertIn("missing top-level keys: ['contributors']", error_text)

    def test_react_generated_validation_rejects_missing_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            generated_dir = Path(tmp_dir)
            (generated_dir / "ecosystems.json").write_text("[]", encoding="utf-8")
            (generated_dir / "snapshotIndex.json").write_text("[]", encoding="utf-8")

            result = validate_react_generated_indexes(generated_dir)

        self.assertFalse(result.ok)
        self.assertIn("proposalLinkIndex.json", "\n".join(result.errors))

    def test_ground_truth_validation_rejects_invalid_curated_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            csv_path = (
                root / "ip_data" / "bitcoin" / "ground_truth" / "interrelations.csv"
            )
            csv_path.parent.mkdir(parents=True)
            csv_path.write_text(
                "\n".join(
                    [
                        "source,target,relation_type,confidence,evidence,note,reviewer,reviewed_at",
                        "bips:44,bips:32,depends_on,high,Requires: 32,,rbo,2026-06-22",
                        "bips:44,bips:32,supersedes,medium,Duplicate pair conflict,,rbo,2026-06-22",
                        "bips:79,bips:78,superseded_by,high,Proposed-Replacement: 78,,rbo,2026-06-22",
                        "oops,bips:33,depends_on,maybe,Bad source format,,rbo,2026-99-99",
                        "slips:39,bips:32,,high,Missing relation type,,,,2026-06-22",
                    ]
                ),
                encoding="utf-8",
            )

            ecosystem_config = {
                "sources": {
                    "bips": {
                        "proposal_acronym": "BIP",
                        "reference_pattern": r"\bBIP[-#\s]?(\d+)\b",
                        "max_proposal_id": 9999,
                    },
                    "slips": {
                        "proposal_acronym": "SLIP",
                        "reference_pattern": r"\bSLIP[-#\s]?(\d+)\b",
                        "max_proposal_id": 9999,
                    },
                }
            }

            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                result = validate_ground_truth_curated_file(
                    "bitcoin", ecosystem_config=ecosystem_config
                )
            finally:
                os.chdir(previous_cwd)

        self.assertFalse(result.ok)
        error_text = "\n".join(result.errors)
        self.assertIn("conflicting relation types", error_text)
        self.assertIn("must use source_slug:id format", error_text)
        self.assertIn("invalid confidence `maybe`", error_text)
        self.assertIn("invalid `reviewed_at` date `2026-99-99`", error_text)
        self.assertIn("missing `relation_type`", error_text)
        self.assertIn("missing `reviewer`", error_text)

    def test_ips_validation_rejects_invalid_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            csv_path = root / "ip_data" / "bitcoin" / "ground_truth" / "ips.csv"
            csv_path.parent.mkdir(parents=True)
            csv_path.write_text(
                "\n".join(
                    [
                        "ip,reviewer,reviewed_at,sampling_strategy,density_bucket,density_basis,created",
                        "bips:44,rbo,2026-06-22,sampler,low,llm_only,2014-04-24",
                        "bips:44,rbo,2026-06-23,manual,-,-,2014-04-24",
                        "bips:45,,2026-06-23,manual,-,-,2014-04-24",
                        "oops,rbo,2026-99-99,invalid_strategy,sideways,2012-04-11,not-a-date",
                    ]
                ),
                encoding="utf-8",
            )

            ecosystem_config = {
                "sources": {
                    "bips": {
                        "proposal_acronym": "BIP",
                        "reference_pattern": r"\bBIP[-#\s]?(\d+)\b",
                        "max_proposal_id": 9999,
                    },
                }
            }

            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                result = validate_ground_truth_ips_file(
                    "bitcoin", ecosystem_config=ecosystem_config
                )
            finally:
                os.chdir(previous_cwd)

        self.assertFalse(result.ok)
        error_text = "\n".join(result.errors)
        self.assertIn("duplicate reviewed IP", error_text)
        self.assertIn("must use source_slug:id format", error_text)
        self.assertIn("invalid `reviewed_at` date `2026-99-99`", error_text)
        self.assertIn("invalid `sampling_strategy` `invalid_strategy`", error_text)
        self.assertIn("invalid `density_bucket` `sideways`", error_text)
        self.assertIn("invalid `density_basis` `2012-04-11`", error_text)
        self.assertIn("invalid `created` date `not-a-date`", error_text)
        self.assertIn("missing `reviewer`", error_text)

    def test_ips_validation_warns_when_rows_fall_outside_declared_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            csv_path = root / "ip_data" / "bitcoin" / "ground_truth" / "ips.csv"
            csv_path.parent.mkdir(parents=True)
            csv_path.write_text(
                "\n".join(
                    [
                        "ip\treviewer\treviewed_at\tsampling_strategy\tdensity_bucket\tdensity_basis\tcreated\ttype",
                        "bips:44\trbo\t2026-06-22\tsampler\tlow\tall_methods\t2014-04-24\tSpecification",
                        "slips:55\trbo\t2026-06-22\tmanual\t-\t-\t2015-01-01\tStandard",
                        "bolts:2\trbo\t2026-06-22\tmanual\t-\t-\t2019-03-01\tStandard",
                        "bips:78\trbo\t2026-06-22\tmanual\t-\t-\t2018-12-01\tInformational",
                    ]
                ),
                encoding="utf-8",
            )

            ecosystem_config = {
                "sources": {
                    "bips": {
                        "proposal_acronym": "BIP",
                        "reference_pattern": r"\bBIP[-#\s]?(\d+)\b",
                        "max_proposal_id": 9999,
                    },
                    "slips": {
                        "proposal_acronym": "SLIP",
                        "reference_pattern": r"\bSLIP[-#\s]?(\d+)\b",
                        "max_proposal_id": 9999,
                    },
                    "bolts": {
                        "proposal_acronym": "BOLT",
                        "reference_pattern": r"\bBOLT[-#\s]?(\d+)\b",
                        "max_proposal_id": 9999,
                    },
                }
            }

            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                result = validate_ground_truth_ips_file(
                    "bitcoin", ecosystem_config=ecosystem_config
                )
            finally:
                os.chdir(previous_cwd)

        self.assertTrue(result.ok)
        self.assertEqual("⚠️ policy", result.file_status["reviewed_ips"])
        warning_text = "\n".join(result.warnings)
        self.assertIn("expects source `bips, slips`", warning_text)
        self.assertIn("bolts:2", warning_text)
        # bips has no required_type restriction: it intentionally samples
        # across all proposal types to match catalog-wide ratios, so an
        # Informational row is not a policy violation.
        self.assertNotIn("expects proposal type", warning_text)
        self.assertNotIn("slips:55", warning_text)

    def test_ground_truth_validation_rejects_inconsistent_review_scope_dates_and_timeline(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            gt_dir = root / "ip_data" / "bitcoin" / "ground_truth"
            gt_dir.mkdir(parents=True)
            (gt_dir / "interrelations.csv").write_text(
                "\n".join(
                    [
                        "source\ttarget\trelation_type\tconfidence\tevidence\tnote\treviewer\treviewed_at",
                        "bips:44\tbips:32\tdepends_on\thigh\tRequires: 32\t\trbo\t2026-06-23",
                        "bips:55\tbips:32\treferences\tmedium\tMentioned in rationale\t\trbo\t2026-06-22",
                        "bips:44\tbips:77\treferences\tmedium\tMentioned in rationale\t\trbo\t2026-06-22",
                    ]
                ),
                encoding="utf-8",
            )
            (gt_dir / "ips.csv").write_text(
                "\n".join(
                    [
                        "ip\treviewer\treviewed_at\tsampling_strategy\tsampling_snapshot\tsampling_seed\tera_bucket\tdensity_bucket\tdensity_basis\tcreated\tstatus\ttype\tlayer\ttitle\textracted_target_count\tnote",
                        "bips:44\trbo\t2026-06-22\tmanual\t\t\tmiddle\tlow\tall_methods\t2014-04-24\tDraft\tSpecification\tApplications\tTest BIP 44\t1\t",
                    ]
                ),
                encoding="utf-8",
            )

            ecosystem_config = {
                "sources": {
                    "bips": self._source_config(root, "bips"),
                }
            }
            preprocess_dir = (
                Path(ecosystem_config["sources"]["bips"]["preprocess"]) / "2026-06-29"
            )
            preprocess_dir.mkdir(parents=True)
            for proposal_id, created, title, last_commit in [
                ("32", "2012-02-11", "BIP 32", "Thu Jun 20 09:00:00 2026 +0000"),
                ("44", "2014-04-24", "BIP 44", "Thu Jun 20 09:00:00 2026 +0000"),
                ("55", "2017-01-01", "BIP 55", "Thu Jun 20 09:00:00 2026 +0000"),
                ("77", "2026-06-25", "BIP 77", "Thu Jun 25 09:00:00 2026 +0000"),
            ]:
                (preprocess_dir / f"bip-{int(proposal_id):04d}.json").write_text(
                    json.dumps(
                        {
                            "raw": {
                                "preamble": {
                                    "bip": proposal_id,
                                    "created": created,
                                    "title": title,
                                }
                            },
                            "meta": {"last_commit": last_commit},
                        }
                    ),
                    encoding="utf-8",
                )

            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                result = validate_ground_truth_curated_file(
                    "bitcoin", ecosystem_config=ecosystem_config
                )
            finally:
                os.chdir(previous_cwd)

        self.assertFalse(result.ok)
        self.assertEqual("❌ consistency", result.file_status["ground_truth"])
        error_text = "\n".join(result.errors)
        self.assertIn("must also appear in `ips.csv`", error_text)
        self.assertIn("must be on or after the curated edge reviewed_at", error_text)
        self.assertIn(
            "newer than the latest known commit date of source `bips:44`", error_text
        )

    def test_ground_truth_workbook_can_be_validated_without_recreating_csvs(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            gt_dir = root / "ip_data" / "bitcoin" / "ground_truth"
            gt_dir.mkdir(parents=True)
            (gt_dir / "interrelations.csv").write_text(
                "\n".join(
                    [
                        "source\ttarget\trelation_type\tconfidence\tevidence\tnote\treviewer\treviewed_at",
                        "bips:44\tbips:32\tdepends_on\thigh\tRequires: 32\t\trbo\t2026-06-22",
                    ]
                ),
                encoding="utf-8",
            )
            (gt_dir / "ips.csv").write_text(
                "\n".join(
                    [
                        "ip\treviewer\treviewed_at\tsampling_strategy\tsampling_snapshot\tsampling_seed\tera_bucket\tdensity_bucket\tdensity_basis\tcreated\tstatus\ttype\tlayer\ttitle\textracted_target_count\tnote",
                        "bips:44\trbo\t2026-06-22\tmanual\t\t\tmiddle\tlow\tall_methods\t2014-04-24\tDraft\tSpecification\tApplications\tTest BIP\t1\t",
                    ]
                ),
                encoding="utf-8",
            )

            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                workbook_path = export_ground_truth_workbook("bitcoin")
                (gt_dir / "interrelations.csv").unlink()
                (gt_dir / "ips.csv").unlink()
                ecosystem_config = {
                    "sources": {
                        "bips": {
                            "proposal_acronym": "BIP",
                            "reference_pattern": r"\bBIP[-#\s]?(\d+)\b",
                            "max_proposal_id": 9999,
                        },
                    }
                }
                curated_result = validate_ground_truth_curated_file(
                    "bitcoin", ecosystem_config=ecosystem_config
                )
                ips_result = validate_ground_truth_ips_file(
                    "bitcoin", ecosystem_config=ecosystem_config
                )
            finally:
                os.chdir(previous_cwd)

            self.assertTrue(workbook_path.exists())
            self.assertTrue(curated_result.ok)
            self.assertTrue(ips_result.ok)
            self.assertFalse((gt_dir / "interrelations.csv").exists())
            self.assertFalse((gt_dir / "ips.csv").exists())

    def test_expected_combined_snapshot_targets_uses_source_snapshot_intersection(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            bips = self._source_config(root, "bips")
            slips = self._source_config(root, "slips")
            nips = self._source_config(root, "nips")

            for snapshot in ("2026-05-28", "2026-03-16", "2021-01-01"):
                (Path(bips["postprocess"]) / snapshot).mkdir(parents=True)
            for snapshot in ("2026-05-28", "2026-03-16"):
                (Path(slips["postprocess"]) / snapshot).mkdir(parents=True)
            for snapshot in ("2026-05-28",):
                (Path(nips["postprocess"]) / snapshot).mkdir(parents=True)

            targets = expected_combined_snapshot_targets(
                "bitcoin",
                ecosystem_config={
                    "sources": {"bips": bips, "slips": slips, "nips": nips}
                },
            )

        self.assertEqual(
            targets,
            [
                ("bips+nips", "2026-05-28"),
                ("bips+slips", "2026-05-28"),
                ("bips+slips", "2026-03-16"),
                ("nips+slips", "2026-05-28"),
                ("bips+nips+slips", "2026-05-28"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
