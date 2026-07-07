#!/usr/bin/env python3
"""Validate snapshot preprocess, analysis, postprocess, and React generated artifacts."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.validation.snapshots import (
    PAYLOAD_COLUMN_LABELS,
    SnapshotValidationResult,
    expected_combined_snapshot_targets,
    validate_combined_snapshot,
    validate_ground_truth_curated_file,
    validate_ground_truth_ips_file,
    validate_payload_index,
    validate_payload_snapshot,
    validate_preprocess_snapshot,
    validate_react_generated_indexes,
)
from ecosystems import ECOSYSTEM_REGISTRY

ANALYSIS_ROOT = Path("ip_data")
OK = "✅"
FAIL = "❌"
NO_SOURCE = "—"


def snapshot_key(ecosystem: str, source: str | None, snapshot: str) -> str:
    if source:
        return f"{ecosystem}/{source}/{snapshot}"
    return f"{ecosystem}/{snapshot}"


def _merge_results(*results: SnapshotValidationResult) -> SnapshotValidationResult:
    merged = SnapshotValidationResult()
    for result in results:
        merged.merge(result)
    return merged


def _source_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ecosystem, ecosystem_config in sorted(ECOSYSTEM_REGISTRY.items()):
        for source, source_config in sorted(
            (ecosystem_config.get("sources") or {}).items()
        ):
            postprocess_root = Path(str(source_config.get("postprocess", "")))
            if not postprocess_root.is_dir():
                continue
            for snapshot_dir in sorted(postprocess_root.iterdir(), reverse=True):
                if not snapshot_dir.is_dir():
                    continue
                snapshot = snapshot_dir.name
                result = _merge_results(
                    validate_preprocess_snapshot(
                        Path(str(source_config.get("preprocess", ""))) / snapshot,
                        ecosystem_slug=ecosystem,
                        source_slug=source,
                        source_config=source_config,
                        ecosystem_config=ecosystem_config,
                    ),
                    validate_payload_snapshot(snapshot_dir),
                    validate_payload_index(snapshot_dir),
                )
                rows.append(
                    {
                        "ecosystem": ecosystem,
                        "source": source,
                        "snapshot": snapshot,
                        "stats": result.stats,
                        "file_status": result.file_status,
                        "errors": result.errors,
                        "warnings": result.warnings,
                        "ok": result.ok,
                    }
                )
    return rows


def _combined_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ecosystem, ecosystem_config in sorted(ECOSYSTEM_REGISTRY.items()):
        sources = ecosystem_config.get("sources") or {}
        if len(sources) < 2:
            continue
        for combo_key, snapshot in expected_combined_snapshot_targets(
            ecosystem, ecosystem_config
        ):
            result = validate_combined_snapshot(
                ecosystem_slug=ecosystem,
                combo_key=combo_key,
                snapshot=snapshot,
            )
            rows.append(
                {
                    "ecosystem": ecosystem,
                    "source": combo_key,
                    "snapshot": snapshot,
                    "stats": result.stats,
                    "file_status": result.file_status,
                    "errors": result.errors,
                    "warnings": result.warnings,
                    "ok": result.ok,
                }
            )
    return rows


def _ground_truth_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ecosystem, ecosystem_config in sorted(ECOSYSTEM_REGISTRY.items()):
        result = validate_ground_truth_curated_file(
            ecosystem, ecosystem_config=ecosystem_config
        )
        result.merge(
            validate_ground_truth_ips_file(ecosystem, ecosystem_config=ecosystem_config)
        )
        rows.append(
            {
                "ecosystem": ecosystem,
                "stats": result.stats,
                "file_status": result.file_status,
                "errors": result.errors,
                "warnings": result.warnings,
                "ok": result.ok,
            }
        )
    return rows


def build_summary(
    rows: list[dict[str, Any]],
    ground_truth_rows: list[dict[str, Any]],
    generated_result: SnapshotValidationResult,
) -> str:
    lines: list[str] = []

    if not rows:
        lines.append(
            "⚠️ No snapshots found under configured `04_postprocess` directories."
        )
    else:
        lines.append("### Artifact Validation")
        lines.append("")

        file_cols = (
            ["preprocess"] + list(PAYLOAD_COLUMN_LABELS.values()) + ["payload_index"]
        )
        header = [
            "Ecosystem",
            "Source",
            "Snapshot",
            "Proposals",
            "LLM edges",
        ] + file_cols
        lines.append("| " + " | ".join(header) + " |")
        lines.append("|:---|:---|:---|---:|---:" + "|:---:" * len(file_cols) + "|")

        for row in rows:
            stats = row["stats"]
            cells = [
                row["ecosystem"],
                row["source"] or NO_SOURCE,
                row["snapshot"],
                str(stats.get("proposals", stats.get("proposal_json", "—"))),
                str(stats.get("llm", "—")),
            ] + [row["file_status"].get(col, "—") for col in file_cols]
            lines.append("| " + " | ".join(cells) + " |")

    lines.append("")
    lines.append("### Ground Truth Validation")
    lines.append("")
    lines.append(
        "| Ecosystem | GT CSV | IPs CSV | Curated edges | Reviewed IPs | Completed reviews |"
    )
    lines.append("|:---|:---:|:---:|---:|---:|---:|")
    for row in ground_truth_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row["ecosystem"],
                    row["file_status"].get("ground_truth", "—"),
                    row["file_status"].get("reviewed_ips", "—"),
                    str(row["stats"].get("ground_truth_edges", "—")),
                    str(row["stats"].get("reviewed_ips", "—")),
                    str(row["stats"].get("completed_reviewed_ips", "—")),
                ]
            )
            + " |"
        )

    lines.append("")
    lines.append("### React Generated Indexes")
    lines.append("")
    lines.append(generated_result.file_status.get("react_generated", FAIL))

    errors_by_snapshot = {
        snapshot_key(row["ecosystem"], row["source"], row["snapshot"]): row["errors"]
        for row in rows
        if row["errors"]
    }
    errors_by_snapshot.update(
        {
            f"{row['ecosystem']}/ground_truth": row["errors"]
            for row in ground_truth_rows
            if row["errors"]
        }
    )
    if generated_result.errors:
        errors_by_snapshot["react/src/generated"] = generated_result.errors

    if errors_by_snapshot:
        lines.append("")
        lines.append("### Errors")
        lines.append("")
        for key, errors in errors_by_snapshot.items():
            lines.append(f"**`{key}`**")
            for error in errors:
                lines.append(f"- {error}")
            lines.append("")

    warnings_by_snapshot = {
        snapshot_key(row["ecosystem"], row["source"], row["snapshot"]): row["warnings"]
        for row in rows
        if row.get("warnings")
    }
    warnings_by_snapshot.update(
        {
            f"{row['ecosystem']}/ground_truth": row["warnings"]
            for row in ground_truth_rows
            if row.get("warnings")
        }
    )

    if warnings_by_snapshot:
        lines.append("")
        lines.append("### Warnings")
        lines.append("")
        for key, warnings in warnings_by_snapshot.items():
            lines.append(f"**`{key}`**")
            for warning in warnings:
                lines.append(f"- {warning}")
            lines.append("")

    return "\n".join(lines)


def main() -> None:
    rows = _source_rows() + _combined_rows()
    ground_truth_rows = _ground_truth_rows()
    generated_result = validate_react_generated_indexes()
    all_ok = (
        generated_result.ok
        and all(row["ok"] for row in rows)
        and all(row["ok"] for row in ground_truth_rows)
    )

    summary = build_summary(rows, ground_truth_rows, generated_result)
    print(summary)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write(summary + "\n")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
