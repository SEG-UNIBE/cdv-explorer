import json
import os
import tempfile
import unittest
from pathlib import Path

from analysis.validation.snapshots import (
    validate_ground_truth_curated_file,
    validate_ground_truth_reviewed_ips_file,
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
            csv_path = root / "ip_data" / "bitcoin" / "ground_truth" / "interrelations.csv"
            csv_path.parent.mkdir(parents=True)
            csv_path.write_text(
                "\n".join([
                    "source,target,relation_type,confidence,evidence,note,reviewer,reviewed_at",
                    "bips:44,bips:32,depends_on,high,Requires: 32,,rbo,2026-06-22",
                    "bips:44,bips:32,supersedes,medium,Duplicate pair conflict,,rbo,2026-06-22",
                    "oops,bips:33,depends_on,maybe,Bad source format,,rbo,2026-99-99",
                    "slips:39,bips:32,,high,Missing relation type,,rbo,2026-06-22",
                ]),
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
                result = validate_ground_truth_curated_file("bitcoin", ecosystem_config=ecosystem_config)
            finally:
                os.chdir(previous_cwd)

        self.assertFalse(result.ok)
        error_text = "\n".join(result.errors)
        self.assertIn("conflicting relation types", error_text)
        self.assertIn("must use source_slug:id format", error_text)
        self.assertIn("invalid confidence `maybe`", error_text)
        self.assertIn("invalid `reviewed_at` date `2026-99-99`", error_text)
        self.assertIn("missing `relation_type`", error_text)

    def test_reviewed_ips_validation_rejects_invalid_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            csv_path = root / "ip_data" / "bitcoin" / "ground_truth" / "reviewed_ips.csv"
            csv_path.parent.mkdir(parents=True)
            csv_path.write_text(
                "\n".join([
                    "ip,reviewer,reviewed_at,sampling_strategy",
                    "bips:44,rbo,2026-06-22,sampler",
                    "bips:44,rbo,2026-06-23,manual",
                    "oops,rbo,2026-99-99,manual",
                ]),
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
                result = validate_ground_truth_reviewed_ips_file("bitcoin", ecosystem_config=ecosystem_config)
            finally:
                os.chdir(previous_cwd)

        self.assertFalse(result.ok)
        error_text = "\n".join(result.errors)
        self.assertIn("duplicate reviewed IP", error_text)
        self.assertIn("must use source_slug:id format", error_text)
        self.assertIn("invalid `reviewed_at` date `2026-99-99`", error_text)


if __name__ == "__main__":
    unittest.main()
