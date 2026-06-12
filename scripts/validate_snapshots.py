#!/usr/bin/env python3
"""Validate snapshot analysis artifacts and write a summary to $GITHUB_STEP_SUMMARY."""

import json
import os
import sys
from pathlib import Path

ANALYSIS_ROOT = Path("ip_data")

REQUIRED_FILES: dict[str, list[str]] = {
    "dependencies/network_data.json":             ["nodes", "dependency_edges"],
    "dependencies/dependency_metrics.json":        ["by_approach", "pairwise_comparisons"],
    "authorship/authorship_payload.json":          ["meta", "top_authors", "bips_per_year", "top_10_share"],
    "classification/classification_payload.json":  ["meta", "sankey_grouped", "status_over_time"],
    "evolution/evolution_payload.json":            ["meta", "status_evolution", "proposal_timelines"],
    "conformity/conformity_metrics.json":          ["per_proposal"],
}

COLUMN_LABELS: dict[str, str] = {
    "dependencies/network_data.json":             "network",
    "dependencies/dependency_metrics.json":        "dep_metrics",
    "authorship/authorship_payload.json":          "authorship",
    "classification/classification_payload.json":  "classification",
    "evolution/evolution_payload.json":            "evolution",
    "conformity/conformity_metrics.json":          "conformity",
}


OK = "✅"
FAIL = "❌"
NO_SOURCE = "—"


def check_snapshot(snapshot_dir: Path) -> dict:
    result: dict = {"ok": True, "errors": [], "stats": {}, "file_status": {}}

    for rel_path, required_keys in REQUIRED_FILES.items():
        label = COLUMN_LABELS[rel_path]
        file_path = snapshot_dir / rel_path

        if not file_path.exists():
            result["file_status"][label] = f"{FAIL} missing"
            result["errors"].append(f"`{rel_path}` is missing")
            result["ok"] = False
            continue

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            result["file_status"][label] = f"{FAIL} bad JSON"
            result["errors"].append(f"`{rel_path}` is not valid JSON: {exc}")
            result["ok"] = False
            continue

        missing_keys = [k for k in required_keys if k not in data]
        if missing_keys:
            result["file_status"][label] = f"{FAIL} keys"
            result["errors"].append(f"`{rel_path}` missing top-level keys: {missing_keys}")
            result["ok"] = False
        else:
            result["file_status"][label] = OK

        if rel_path == "dependencies/network_data.json":
            result["stats"]["proposals"] = len(data.get("nodes", []))
            result["stats"]["llm"] = sum(
                1
                for edge in data.get("dependency_edges", [])
                if edge.get("extraction_method") == "body_extracted_llm"
            )

    return result


def build_summary(rows: list[dict], errors_by_snapshot: dict[str, list[str]]) -> str:
    lines: list[str] = []

    if not rows:
        lines.append("⚠️ No snapshots found under `ip_data/*/03_analysis/` or `ip_data/*/*/03_analysis/`.")
        return "\n".join(lines)

    lines.append("### Artifact Validation")
    lines.append("")

    file_cols = list(COLUMN_LABELS.values())
    header = ["Ecosystem", "Source", "Snapshot", "Proposals", "LLM edges"] + file_cols
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|:---|:---|:---|---:|---:" + "|:---:" * len(file_cols) + "|")

    for row in rows:
        stats = row["stats"]
        cells = [
            row["ecosystem"],
            row["source"],
            row["snapshot"],
            str(stats.get("proposals", "—")),
            str(stats.get("llm", "—")),
        ] + [row["file_status"].get(col, "—") for col in file_cols]
        lines.append("| " + " | ".join(cells) + " |")

    lines.append("")

    if errors_by_snapshot:
        lines.append("### Errors")
        lines.append("")
        for key, errs in errors_by_snapshot.items():
            lines.append(f"**`{key}`**")
            for err in errs:
                lines.append(f"- {err}")
            lines.append("")

    return "\n".join(lines)


def snapshot_key(ecosystem: str, source: str | None, snapshot: str) -> str:
    if source:
        return f"{ecosystem}/{source}/{snapshot}"
    return f"{ecosystem}/{snapshot}"


def analysis_dirs_for_ecosystem(ecosystem_dir: Path) -> list[tuple[str | None, Path]]:
    # Support ip_data/<ecosystem>/03_analysis, ip_data/<ecosystem>/<source>/03_analysis,
    # and ip_data/<ecosystem>/_combined/<combo>/03_analysis.
    candidate = ecosystem_dir / "03_analysis"
    if candidate.is_dir():
        return [(None, candidate)]

    analysis_dirs = [
        (p.name, p / "03_analysis") for p in sorted(ecosystem_dir.iterdir())
        if p.is_dir() and p.name != "_combined" and (p / "03_analysis").is_dir()
    ]
    combined_root = ecosystem_dir / "_combined"
    if combined_root.is_dir():
        analysis_dirs.extend(
            (p.name, p / "03_analysis") for p in sorted(combined_root.iterdir())
            if p.is_dir() and (p / "03_analysis").is_dir()
        )
    return analysis_dirs


def main() -> None:
    rows: list[dict] = []
    errors_by_snapshot: dict[str, list[str]] = {}
    all_ok = True

    for ecosystem_dir in sorted(ANALYSIS_ROOT.iterdir()):
        if not ecosystem_dir.is_dir():
            continue
        analysis_dirs = analysis_dirs_for_ecosystem(ecosystem_dir)
        ecosystem = ecosystem_dir.name

        for source, analysis_dir in analysis_dirs:
            for snapshot_dir in sorted(analysis_dir.iterdir(), reverse=True):
                if not snapshot_dir.is_dir():
                    continue
                snapshot = snapshot_dir.name
                checked = check_snapshot(snapshot_dir)

                if not checked["ok"]:
                    all_ok = False
                    errors_by_snapshot[snapshot_key(ecosystem, source, snapshot)] = checked["errors"]

                rows.append({
                    "ecosystem": ecosystem,
                    "source": source or NO_SOURCE,
                    "snapshot": snapshot,
                    "stats": checked["stats"],
                    "file_status": checked["file_status"],
                })

    summary = build_summary(rows, errors_by_snapshot)
    print(summary)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write(summary + "\n")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
