import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import typer

from main import _rebuild_source_artifacts


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


if __name__ == "__main__":
    unittest.main()
