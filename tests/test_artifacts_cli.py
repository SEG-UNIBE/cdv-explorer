import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import typer
from typer.testing import CliRunner

from analysis.validation import SnapshotValidationResult
from main import app, _common_preprocess_snapshot_labels, _rebuild_source_artifacts


runner = CliRunner()


class ArtifactRebuildTests(unittest.TestCase):
    def _source_config(self, root: Path) -> dict:
        return {
            "harvest": str(root / "01_harvest"),
            "preprocess": str(root / "02_preprocess"),
            "analysis": str(root / "03_analysis"),
            "postprocess": str(root / "04_postprocess"),
            "primary_id_field": "bip",
            "proposal_acronym": "BIP",
            "document_prefix": "bip",
        }

    def test_rebuilds_artifacts_from_existing_preprocess_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src = self._source_config(root)
            preprocess_dir = root / "02_preprocess" / "2026-05-28"
            preprocess_dir.mkdir(parents=True)
            (preprocess_dir / "bip-0001.json").write_text("{}", encoding="utf-8")
            (root / "01_harvest").mkdir()

            with (
                patch(
                    "main._run_stage",
                    side_effect=lambda _name, _total, _unit, runner: runner(lambda *_args, **_kwargs: None),
                ),
                patch("analysis.pipeline.prepare_ecosystem_artifacts") as prepare,
                patch("analysis.validation.validate_source_snapshot", return_value=SnapshotValidationResult()),
            ):
                _rebuild_source_artifacts("bitcoin", "bips", src, "2026-05-28")

            prepare.assert_called_once()
            kwargs = prepare.call_args.kwargs
            self.assertEqual(kwargs["proposal_json_dir"], preprocess_dir)
            self.assertEqual(kwargs["artifact_root"], root / "03_analysis")
            self.assertEqual(kwargs["postprocess_root"], root / "04_postprocess")
            self.assertEqual(kwargs["snapshot"], "2026-05-28")
            self.assertEqual(kwargs["id_field"], "bip")
            self.assertEqual(kwargs["proposal_label"], "BIP")
            self.assertEqual(kwargs["repo_dir"], root / "01_harvest")
            self.assertEqual(kwargs["file_prefix"], "bip")
            self.assertEqual(kwargs["source_context"].ecosystem_slug, "bitcoin")
            self.assertEqual(kwargs["source_context"].source_slug, "bips")

    def test_rebuild_fails_when_preprocess_snapshot_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            src = self._source_config(Path(tmp_dir))

            with self.assertRaises(typer.Exit):
                _rebuild_source_artifacts("bitcoin", "bips", src, "2026-05-28")

    def test_common_preprocess_snapshots_use_intersection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            bips = self._source_config(root / "bips")
            slips = self._source_config(root / "slips")
            for src, snapshots in (
                (bips, ["2021-01-01", "2026-03-16", "2026-05-28"]),
                (slips, ["2026-03-16", "2026-05-28", "2027-01-01"]),
            ):
                for snapshot in snapshots:
                    (Path(src["preprocess"]) / snapshot).mkdir(parents=True)

            snapshots = _common_preprocess_snapshot_labels({"bips": bips, "slips": slips})

            self.assertEqual(snapshots, ["2026-03-16", "2026-05-28"])

    def test_rebuild_all_artifacts_rebuilds_every_common_preprocess_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            bips = self._source_config(root / "bips")
            slips = self._source_config(root / "slips")
            for src in (bips, slips):
                for snapshot in ("2026-03-16", "2026-05-28"):
                    preprocess_dir = Path(src["preprocess"]) / snapshot
                    preprocess_dir.mkdir(parents=True)
                    (preprocess_dir / "proposal.json").write_text("{}", encoding="utf-8")

            ecosystem = {"slug": "bitcoin", "sources": {"bips": bips, "slips": slips}}
            with (
                patch.dict("main.ECOSYSTEM_REGISTRY", {"bitcoin": ecosystem}, clear=True),
                patch("main._rebuild_artifacts_for_targets") as rebuild,
            ):
                result = runner.invoke(app, ["artifacts", "rebuild", "-e", "bitcoin", "--all"])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual([call.args[3] for call in rebuild.call_args_list], ["2026-03-16", "2026-05-28"])

    def test_ground_truth_sampling_prefills_reviewed_ips_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            analysis_root = root / "bips" / "03_analysis" / "2026-05-28" / "dependencies"
            analysis_root.mkdir(parents=True)
            (analysis_root / "network_data.json").write_text(
                """
                {
                  "nodes": [
                    {"id": "1", "created": "2012-01-01", "status": "Draft", "type": "Process", "layer": "", "title": "One"},
                    {"id": "2", "created": "2016-01-01", "status": "Final", "type": "Standard", "layer": "", "title": "Two"},
                    {"id": "3", "created": "2024-01-01", "status": "Draft", "type": "Standard", "layer": "", "title": "Three"}
                  ],
                  "dependency_edges": [
                    {"source": "bips:2", "target": "bips:1", "extraction_method": "body_extracted_regex", "relation_type": "reference", "value": 1},
                    {"source": "bips:3", "target": "bips:1", "extraction_method": "body_extracted_llm", "relation_type": "implicit_dependency", "value": 1},
                    {"source": "bips:3", "target": "bips:2", "extraction_method": "preamble_extracted", "relation_type": "requires", "value": 1}
                  ]
                }
                """,
                encoding="utf-8",
            )

            ecosystem = {
                "slug": "bitcoin",
                "sources": {
                    "bips": {
                        **self._source_config(root / "bips"),
                        "reference_pattern": r"\\bBIP[-#\\s]?(\\d+)\\b",
                    }
                },
            }
            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                with patch.dict("main.ECOSYSTEM_REGISTRY", {"bitcoin": ecosystem}, clear=True):
                    result = runner.invoke(
                        app,
                        [
                            "ground-truth",
                            "sample-reviewed-ips",
                            "-e",
                            "bitcoin",
                            "--source",
                            "bips",
                            "-s",
                            "2026-05-28",
                            "--count",
                            "2",
                            "--seed",
                            "7",
                        ],
                    )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(result.exit_code, 0, result.output)
            reviewed_csv = root / "ip_data" / "bitcoin" / "ground_truth" / "reviewed_ips.csv"
            self.assertTrue(reviewed_csv.exists())
            content = reviewed_csv.read_text(encoding="utf-8")
            self.assertIn("ip,reviewer,reviewed_at,sampling_strategy", content)
            self.assertIn("bips:", content)


if __name__ == "__main__":
    unittest.main()
