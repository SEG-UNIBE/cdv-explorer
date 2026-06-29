import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import typer
from typer.testing import CliRunner

from analysis.validation.ground_truth import (
    export_ground_truth_workbook,
    load_ground_truth_curated_entries,
    load_ground_truth_ips,
    load_reviewed_ip_append_rows,
    reviewed_ip_append_workbook_path,
)
from analysis.validation import SnapshotValidationResult
from main import (
    app,
    _available_llm_models_in_preprocess_dir,
    _common_preprocess_snapshot_labels,
    _existing_llm_model_run_counts,
    _rebuild_source_artifacts,
    _resolve_artifact_llm_model,
)
from pipeline.preprocess._enrich import _preserved_llm_runs


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
                    side_effect=lambda _name, _total, _unit, runner: runner(
                        lambda *_args, **_kwargs: None
                    ),
                ),
                patch("analysis.pipeline.prepare_ecosystem_artifacts") as prepare,
                patch(
                    "analysis.validation.validate_source_snapshot",
                    return_value=SnapshotValidationResult(),
                ),
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
            self.assertIsNone(kwargs["artifact_llm_model"])

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

            snapshots = _common_preprocess_snapshot_labels(
                {"bips": bips, "slips": slips}
            )

            self.assertEqual(snapshots, ["2026-03-16", "2026-05-28"])

    def test_existing_llm_model_run_counts_only_matching_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            preprocess_dir = Path(tmp_dir) / "02_preprocess" / "2026-05-28"
            preprocess_dir.mkdir(parents=True)
            (preprocess_dir / "bip-0001.json").write_text(
                json.dumps(
                    {
                        "raw": {"preamble": {"bip": "1"}},
                        "insights": {
                            "interrelations": {
                                "body_extracted_llm": [
                                    {
                                        "model": "gpt-5.4-mini",
                                        "timestamp": "2026-06-01T00:00:00Z",
                                        "dependencies": [],
                                    },
                                    {
                                        "model": "gpt-5.4",
                                        "timestamp": "2026-06-02T00:00:00Z",
                                        "dependencies": [],
                                    },
                                ]
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            (preprocess_dir / "bip-0002.json").write_text(
                json.dumps(
                    {
                        "raw": {"preamble": {"bip": "2"}},
                        "insights": {
                            "interrelations": {
                                "body_extracted_llm": [
                                    {
                                        "model": "gpt-5.4-mini",
                                        "timestamp": "2026-06-03T00:00:00Z",
                                        "dependencies": [],
                                    },
                                ]
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            docs, runs = _existing_llm_model_run_counts(
                preprocess_dir,
                id_field="bip",
                llm_model="gpt-5.4-mini",
            )

        self.assertEqual((docs, runs), (2, 2))

    def test_existing_llm_model_run_counts_respects_focus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            preprocess_dir = Path(tmp_dir) / "02_preprocess" / "2026-05-28"
            preprocess_dir.mkdir(parents=True)
            for bip_id in ("1", "2"):
                (preprocess_dir / f"bip-{bip_id.zfill(4)}.json").write_text(
                    json.dumps(
                        {
                            "raw": {"preamble": {"bip": bip_id}},
                            "insights": {
                                "interrelations": {
                                    "body_extracted_llm": [
                                        {
                                            "model": "gpt-5.4-mini",
                                            "timestamp": "2026-06-01T00:00:00Z",
                                            "dependencies": [],
                                        },
                                    ]
                                }
                            },
                        }
                    ),
                    encoding="utf-8",
                )

            docs, runs = _existing_llm_model_run_counts(
                preprocess_dir,
                id_field="bip",
                llm_model="gpt-5.4-mini",
                focus={"1"},
            )

        self.assertEqual((docs, runs), (1, 1))

    def test_available_llm_models_in_preprocess_dir_discovers_distinct_models(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            preprocess_dir = Path(tmp_dir) / "02_preprocess" / "2026-05-28"
            preprocess_dir.mkdir(parents=True)
            (preprocess_dir / "bip-0001.json").write_text(
                json.dumps(
                    {
                        "insights": {
                            "interrelations": {
                                "body_extracted_llm": [
                                    {
                                        "model": "gpt-5.4-mini",
                                        "timestamp": "2026-06-01T00:00:00Z",
                                        "dependencies": [],
                                    },
                                    {
                                        "model": "gpt-5.4",
                                        "timestamp": "2026-06-02T00:00:00Z",
                                        "dependencies": [],
                                    },
                                ]
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            models = _available_llm_models_in_preprocess_dir(preprocess_dir)

        self.assertEqual(models, ["gpt-5.4", "gpt-5.4-mini"])

    def test_resolve_artifact_llm_model_fails_without_explicit_choice_when_multiple_exist(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            preprocess_dir = Path(tmp_dir) / "02_preprocess" / "2026-05-28"
            preprocess_dir.mkdir(parents=True)
            (preprocess_dir / "bip-0001.json").write_text(
                json.dumps(
                    {
                        "insights": {
                            "interrelations": {
                                "body_extracted_llm": [
                                    {
                                        "model": "gpt-5.4-mini",
                                        "timestamp": "2026-06-01T00:00:00Z",
                                        "dependencies": [],
                                    },
                                    {
                                        "model": "gpt-5.4",
                                        "timestamp": "2026-06-02T00:00:00Z",
                                        "dependencies": [],
                                    },
                                ]
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(typer.Exit):
                _resolve_artifact_llm_model(
                    eco_slug="bitcoin",
                    src_slug="bips",
                    snapshot="2026-05-28",
                    preprocess_dir=preprocess_dir,
                    requested_model=None,
                )

    def test_resolve_artifact_llm_model_accepts_requested_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            preprocess_dir = Path(tmp_dir) / "02_preprocess" / "2026-05-28"
            preprocess_dir.mkdir(parents=True)
            (preprocess_dir / "bip-0001.json").write_text(
                json.dumps(
                    {
                        "insights": {
                            "interrelations": {
                                "body_extracted_llm": [
                                    {
                                        "model": "gpt-5.4-mini",
                                        "timestamp": "2026-06-01T00:00:00Z",
                                        "dependencies": [],
                                    },
                                    {
                                        "model": "gpt-5.4",
                                        "timestamp": "2026-06-02T00:00:00Z",
                                        "dependencies": [],
                                    },
                                ]
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            model = _resolve_artifact_llm_model(
                eco_slug="bitcoin",
                src_slug="bips",
                snapshot="2026-05-28",
                preprocess_dir=preprocess_dir,
                requested_model="gpt-5.4-mini",
            )

        self.assertEqual(model, "gpt-5.4-mini")

    def test_preserved_llm_runs_replaces_only_same_model(self) -> None:
        raw_llm = [
            {
                "model": "gpt-5.4-mini",
                "timestamp": "2026-06-01T00:00:00Z",
                "dependencies": [{"target": "bips:1"}],
            },
            {
                "model": "gpt-5.4",
                "timestamp": "2026-06-02T00:00:00Z",
                "dependencies": [{"target": "bips:2"}],
            },
        ]

        preserved = _preserved_llm_runs(raw_llm, "gpt-5.4-mini", True)

        self.assertEqual(
            preserved,
            [
                {
                    "model": "gpt-5.4",
                    "timestamp": "2026-06-02T00:00:00Z",
                    "dependencies": [{"target": "bips:2"}],
                },
            ],
        )

    def test_rebuild_all_artifacts_rebuilds_every_common_preprocess_snapshot(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            bips = self._source_config(root / "bips")
            slips = self._source_config(root / "slips")
            for src in (bips, slips):
                for snapshot in ("2026-03-16", "2026-05-28"):
                    preprocess_dir = Path(src["preprocess"]) / snapshot
                    preprocess_dir.mkdir(parents=True)
                    (preprocess_dir / "proposal.json").write_text(
                        "{}", encoding="utf-8"
                    )

            ecosystem = {"slug": "bitcoin", "sources": {"bips": bips, "slips": slips}}
            with (
                patch.dict(
                    "main.ECOSYSTEM_REGISTRY", {"bitcoin": ecosystem}, clear=True
                ),
                patch("main._rebuild_artifacts_for_targets") as rebuild,
            ):
                result = runner.invoke(
                    app, ["artifacts", "rebuild", "-e", "bitcoin", "--all"]
                )

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(
                [call.args[3] for call in rebuild.call_args_list],
                ["2026-03-16", "2026-05-28"],
            )

    def test_ground_truth_sampling_prefills_workbook_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            analysis_root = (
                root / "bips" / "03_analysis" / "2026-05-28" / "dependencies"
            )
            analysis_root.mkdir(parents=True)
            (analysis_root / "network_data.json").write_text(
                """
                {
                  "nodes": [
                    {"id": "1", "created": "2012-01-01", "status": "Draft", "type": "Process", "layer": "", "title": "One"},
                    {"id": "2", "created": "2016-01-01", "status": "Final", "type": "Specification", "layer": "", "title": "Two"},
                    {"id": "3", "created": "2024-01-01", "status": "Draft", "type": "Specification", "layer": "", "title": "Three"}
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
                with patch.dict(
                    "main.ECOSYSTEM_REGISTRY", {"bitcoin": ecosystem}, clear=True
                ):
                    result = runner.invoke(
                        app,
                        [
                            "ground-truth",
                            "sample-ips",
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
                    append_rows = load_reviewed_ip_append_rows("bitcoin")
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(result.exit_code, 0, result.output)
            workbook_path = root / "ip_data" / "bitcoin" / "ground_truth" / "ips_append.xlsx"
            self.assertTrue(workbook_path.exists())
            self.assertEqual(len(append_rows), 2)
            self.assertTrue(
                all(row["ip_source"] == "bips" and row["ip_id"] for row in append_rows)
            )

    def test_ground_truth_sampling_can_filter_to_specific_proposal_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            analysis_root = (
                root / "bips" / "03_analysis" / "2026-05-28" / "dependencies"
            )
            analysis_root.mkdir(parents=True)
            (analysis_root / "network_data.json").write_text(
                """
                {
                  "nodes": [
                    {"id": "1", "created": "2012-01-01", "status": "Draft", "type": "Process", "layer": "", "title": "One"},
                    {"id": "2", "created": "2016-01-01", "status": "Final", "type": "Specification", "layer": "", "title": "Two"},
                    {"id": "3", "created": "2024-01-01", "status": "Draft", "type": "Specification", "layer": "", "title": "Three"}
                  ],
                  "dependency_edges": [
                    {"source": "bips:2", "target": "bips:1", "extraction_method": "body_extracted_regex", "relation_type": "reference", "value": 1},
                    {"source": "bips:3", "target": "bips:1", "extraction_method": "body_extracted_llm", "relation_type": "implicit_dependency", "value": 1}
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
                with patch.dict(
                    "main.ECOSYSTEM_REGISTRY", {"bitcoin": ecosystem}, clear=True
                ):
                    result = runner.invoke(
                        app,
                        [
                            "ground-truth",
                            "sample-ips",
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
                            "--proposal-type",
                            "Specification",
                        ],
                    )
                    append_rows = load_reviewed_ip_append_rows("bitcoin")
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(len(append_rows), 2)
            self.assertTrue(all(row["type"] == "Specification" for row in append_rows))

    def test_ground_truth_sampling_updates_workbook_backed_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            analysis_root = (
                root / "bips" / "03_analysis" / "2026-05-28" / "dependencies"
            )
            analysis_root.mkdir(parents=True)
            (analysis_root / "network_data.json").write_text(
                """
                {
                  "nodes": [
                    {"id": "1", "created": "2012-01-01", "status": "Draft", "type": "Specification", "layer": "", "title": "One"},
                    {"id": "2", "created": "2016-01-01", "status": "Final", "type": "Specification", "layer": "", "title": "Two"},
                    {"id": "3", "created": "2024-01-01", "status": "Draft", "type": "Specification", "layer": "", "title": "Three"}
                  ],
                  "dependency_edges": [
                    {"source": "bips:2", "target": "bips:1", "extraction_method": "body_extracted_regex", "relation_type": "reference", "value": 1},
                    {"source": "bips:3", "target": "bips:1", "extraction_method": "body_extracted_llm", "relation_type": "implicit_dependency", "value": 1}
                  ]
                }
                """,
                encoding="utf-8",
            )

            gt_dir = root / "ip_data" / "bitcoin" / "ground_truth"
            gt_dir.mkdir(parents=True)
            (gt_dir / "ips.csv").write_text(
                "ip\treviewer\treviewed_at\tsampling_strategy\tsampling_snapshot\tsampling_seed\tera_bucket\tdensity_bucket\tdensity_basis\tcreated\tstatus\ttype\tlayer\ttitle\textracted_target_count\tnote\n"
                "bips:1\trbo\t2026-06-29\tmanual\t-\t-\t-\t-\t-\t2012-01-01\tDraft\tSpecification\t\tOne\t0\t\n",
                encoding="utf-8",
            )
            (gt_dir / "interrelations.csv").write_text(
                "source\ttarget\trelation_type\tconfidence\tevidence\tnote\treviewer\treviewed_at\n"
                "bips:1\tbips:2\treferences\thigh\tSee BIP2\t\trbo\t2026-06-29\n",
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
                with patch.dict(
                    "main.ECOSYSTEM_REGISTRY", {"bitcoin": ecosystem}, clear=True
                ):
                    workbook_path = export_ground_truth_workbook("bitcoin")
                    (gt_dir / "ips.csv").unlink()
                    (gt_dir / "interrelations.csv").unlink()

                    result = runner.invoke(
                        app,
                        [
                            "ground-truth",
                            "sample-ips",
                            "-e",
                            "bitcoin",
                            "--source",
                            "bips",
                            "-s",
                            "2026-05-28",
                            "--count",
                            "1",
                            "--seed",
                            "7",
                        ],
                    )

                    self.assertEqual(result.exit_code, 0, result.output)
                    self.assertTrue(workbook_path.exists())
                    append_path = reviewed_ip_append_workbook_path("bitcoin")
                    self.assertTrue(append_path.exists())
                    self.assertFalse((gt_dir / "ips.csv").exists())
                    self.assertFalse((gt_dir / "interrelations.csv").exists())

                    reviewed_rows = load_ground_truth_ips("bitcoin", strict=False)
                    self.assertEqual(len(reviewed_rows), 1)
                    self.assertEqual(
                        sorted(row["ip"] for row in reviewed_rows),
                        ["bips:1"],
                    )
                    append_rows = load_reviewed_ip_append_rows("bitcoin")
                    self.assertEqual(len(append_rows), 1)
                    self.assertNotEqual(
                        f"{append_rows[0]['ip_source']}:{append_rows[0]['ip_id']}",
                        "bips:1",
                    )

                    curated_rows = load_ground_truth_curated_entries(
                        "bitcoin", strict=False
                    )
                    self.assertEqual(len(curated_rows), 1)
                    self.assertEqual(curated_rows[0]["source"], "bips:1")
                    self.assertEqual(curated_rows[0]["target"], "bips:2")
            finally:
                os.chdir(previous_cwd)


if __name__ == "__main__":
    unittest.main()
