import tempfile
import unittest
from pathlib import Path

from cli.snapshots import _collect_snapshot_removal_targets, _remove_snapshot_targets


class SnapshotRemovalTests(unittest.TestCase):
    def test_collects_only_generated_snapshot_dirs_for_selected_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src = {
                "preprocess": str(root / "02_preprocess"),
                "analysis": str(root / "03_analysis"),
                "postprocess": str(root / "04_postprocess"),
            }
            for base in ("02_preprocess", "03_analysis", "04_postprocess"):
                (root / base / "2026-05-28").mkdir(parents=True)
                (root / base / "2026-03-16").mkdir(parents=True)

            eco = {
                "sources": {
                    "nips": src,
                    "other": {**src, "analysis": str(root / "missing")},
                }
            }

            targets = _collect_snapshot_removal_targets(
                "nostr", eco, "nips", "2026-05-28"
            )

        self.assertEqual(
            [path.name for _source, path in targets],
            ["2026-05-28", "2026-05-28", "2026-05-28"],
        )
        self.assertEqual({source for source, _path in targets}, {"nips"})

    def test_removes_collected_snapshot_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            targets = []
            for name in ("02_preprocess", "03_analysis", "04_postprocess"):
                target = root / name / "2026-05-28"
                target.mkdir(parents=True)
                (target / "artifact.json").write_text("{}", encoding="utf-8")
                targets.append(("nips", target))

            _remove_snapshot_targets(targets)

            self.assertFalse(any(target.exists() for _source, target in targets))
            self.assertTrue(all(target.parent.exists() for _source, target in targets))


if __name__ == "__main__":
    unittest.main()
