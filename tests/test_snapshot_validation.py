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
    validate_preprocess_snapshot,
    validate_react_generated_indexes,
    validate_react_snapshot_exports,
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
                                        "model": "gpt-test",
                                        "dependencies": [
                                            {"target": "slips:39"},
                                            {"target": "BIP 32"},
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

    def test_react_snapshot_validation_rejects_missing_index_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            react_dir = Path(tmp_dir) / "react"
            react_dir.mkdir()
            (react_dir / "dataset_index.json").write_text(
                json.dumps({"files": {"network_nodes": "network_nodes.csv"}}),
                encoding="utf-8",
            )

            result = validate_react_snapshot_exports(react_dir)

        self.assertFalse(result.ok)
        self.assertIn("references missing files", "\n".join(result.errors))

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
                        "slips:39,bips:32,,high,Missing relation type,,rbo,2026-06-22",
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
                        "slips:55\trbo\t2026-06-22\tmanual\t-\t-\t2015-01-01\tWallet",
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
        self.assertIn("expects source `bips`", warning_text)
        self.assertIn("expects proposal type `Specification`", warning_text)

    def test_ground_truth_workbook_recreates_csvs_for_validation(self) -> None:
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
            self.assertTrue((gt_dir / "interrelations.csv").exists())
            self.assertTrue((gt_dir / "ips.csv").exists())

    def test_expected_combined_snapshot_targets_uses_source_snapshot_intersection(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            bips = self._source_config(root, "bips")
            slips = self._source_config(root, "slips")
            nips = self._source_config(root, "nips")

            for snapshot in ("2026-05-28", "2026-03-16", "2021-01-01"):
                (Path(bips["analysis"]) / snapshot).mkdir(parents=True)
            for snapshot in ("2026-05-28", "2026-03-16"):
                (Path(slips["analysis"]) / snapshot).mkdir(parents=True)
            for snapshot in ("2026-05-28",):
                (Path(nips["analysis"]) / snapshot).mkdir(parents=True)

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
