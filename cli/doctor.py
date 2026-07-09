"""Root `doctor` command for local environment and artifact validation."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path

import typer
from rich.table import Table

from cli.common import console
from ecosystems import ECOSYSTEM_REGISTRY


def _iter_configured_sources() -> list[tuple[str, str, dict]]:
    rows: list[tuple[str, str, dict]] = []
    for eco_slug, eco in sorted(ECOSYSTEM_REGISTRY.items()):
        for src_slug, src in sorted((eco.get("sources") or {}).items()):
            rows.append((eco_slug, src_slug, src))
    return rows


def _command_version(command: str, *args: str) -> str | None:
    executable = shutil.which(command)
    if executable is None:
        return None
    try:
        result = subprocess.run(
            [executable, *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return executable
    output = (result.stdout or result.stderr).strip().splitlines()
    return output[0] if output else executable


def _latest_snapshot_labels(analysis_root: Path) -> list[str]:
    if not analysis_root.is_dir():
        return []
    return sorted(
        (
            path.name
            for path in analysis_root.iterdir()
            if path.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", path.name)
        ),
        reverse=True,
    )


def _doctor_row(table: Table, status: str, check: str, details: str) -> bool:
    styles = {
        "OK": "[green]OK[/green]",
        "WARN": "[yellow]WARN[/yellow]",
        "FAIL": "[red]FAIL[/red]",
    }
    table.add_row(styles.get(status, status), check, details)
    return status != "FAIL"


def _load_requirements(requirements_path: Path) -> list[str]:
    if not requirements_path.exists():
        return []
    packages: list[str] = []
    for raw_line in requirements_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        name = re.split(r"[<>=!~;\[]", line, maxsplit=1)[0].strip()
        if name:
            packages.append(name)
    return packages


def _ecosystem_llm_model(config: dict) -> str:
    llm_config = config.get("llm", {})
    if not isinstance(llm_config, dict):
        return ""
    return str(llm_config.get("model", "")).strip()


def doctor() -> None:
    """Check local tools, dependencies, configs, and snapshot artifacts without changing files."""
    from analysis.validation import (
        ground_truth_workbook_path,
        reviewed_ip_policy_for_ecosystem,
        validate_ground_truth_ips_file,
    )

    table = Table("Status", "Check", "Details", title="CDV Explorer Doctor")
    ok = True

    ok &= _doctor_row(
        table,
        "OK" if sys.version_info >= (3, 12) else "FAIL",
        "Python",
        f"{sys.version.split()[0]} at {sys.executable}",
    )

    missing_packages: list[str] = []
    installed_count = 0
    for package in _load_requirements(Path("requirements.txt")):
        try:
            metadata.version(package)
            installed_count += 1
        except metadata.PackageNotFoundError:
            missing_packages.append(package)
    ok &= _doctor_row(
        table,
        "FAIL" if missing_packages else "OK",
        "Python packages",
        f"Missing: {', '.join(missing_packages)}"
        if missing_packages
        else f"{installed_count} packages installed",
    )

    git_version = _command_version("git", "--version")
    ok &= _doctor_row(
        table,
        "OK" if git_version else "FAIL",
        "Git",
        git_version or "git not found on PATH",
    )

    node_version = _command_version("node", "--version")
    ok &= _doctor_row(
        table,
        "OK" if node_version else "FAIL",
        "Node.js",
        node_version or "node not found on PATH",
    )

    npm_version = _command_version("npm", "--version")
    ok &= _doctor_row(
        table,
        "OK" if npm_version else "FAIL",
        "npm",
        npm_version or "npm not found on PATH",
    )

    react_node_modules = Path("react/node_modules")
    ok &= _doctor_row(
        table,
        "OK" if react_node_modules.is_dir() else "WARN",
        "React dependencies",
        "react/node_modules present"
        if react_node_modules.is_dir()
        else "Run `cd react && npm install` before frontend work",
    )

    sources = _iter_configured_sources()
    ok &= _doctor_row(
        table,
        "OK" if sources else "FAIL",
        "Ecosystem configs",
        f"{len(ECOSYSTEM_REGISTRY)} ecosystems, {len(sources)} sources",
    )
    ecosystems_missing_llm_model = [
        slug
        for slug, config in ECOSYSTEM_REGISTRY.items()
        if config.get("sources") and not _ecosystem_llm_model(config)
    ]
    ok &= _doctor_row(
        table,
        "WARN" if ecosystems_missing_llm_model else "OK",
        "LLM model config",
        (
            f"Missing llm.model in ecosystems: {', '.join(ecosystems_missing_llm_model)}; "
            "`run --skipllm` still works"
        )
        if ecosystems_missing_llm_model
        else "llm.model configured for ecosystems with sources",
    )

    required_source_keys = {
        "proposal_acronym",
        "harvest",
        "preprocess",
        "analysis",
        "postprocess",
        "document_prefix",
        "primary_id_field",
        "document_file_pattern",
        "reference_pattern",
    }
    config_errors: list[str] = []
    snapshot_details: list[str] = []
    harvest_warnings: list[str] = []
    for eco_slug, src_slug, src in sources:
        missing = sorted(required_source_keys - set(src))
        if missing:
            config_errors.append(f"{eco_slug}/{src_slug}: missing {', '.join(missing)}")

        harvest_root = Path(src.get("harvest", ""))
        if not (harvest_root / ".git").is_dir():
            harvest_warnings.append(f"{eco_slug}/{src_slug}")

        snapshots_for_source = _latest_snapshot_labels(Path(src.get("analysis", "")))
        if snapshots_for_source:
            snapshot_details.append(f"{eco_slug}/{src_slug}: {snapshots_for_source[0]}")
        else:
            snapshot_details.append(f"{eco_slug}/{src_slug}: none")

    ok &= _doctor_row(
        table,
        "FAIL" if config_errors else "OK",
        "Source config schema",
        "; ".join(config_errors) if config_errors else "required source keys present",
    )
    ok &= _doctor_row(
        table,
        "WARN" if harvest_warnings else "OK",
        "Harvest repos",
        f"Not cloned yet: {', '.join(harvest_warnings)}"
        if harvest_warnings
        else "all configured harvest repos are git clones",
    )
    ok &= _doctor_row(
        table,
        "OK" if any(": none" not in detail for detail in snapshot_details) else "WARN",
        "Snapshots",
        "; ".join(snapshot_details) if snapshot_details else "no configured sources",
    )
    reviewed_ip_warnings: list[str] = []
    for eco_slug, eco in sorted(ECOSYSTEM_REGISTRY.items()):
        if not eco.get("sources"):
            continue
        gt_dir = Path("ip_data") / eco_slug / "ground_truth"
        interrelations_csv = gt_dir / "interrelations.csv"
        reviewed_ips_csv = gt_dir / "ips.csv"
        workbook_path = ground_truth_workbook_path(eco_slug)
        has_gt_source = interrelations_csv.exists() or workbook_path.exists()
        if has_gt_source and not (reviewed_ips_csv.exists() or workbook_path.exists()):
            reviewed_ip_warnings.append(eco_slug)
    ok &= _doctor_row(
        table,
        "WARN" if reviewed_ip_warnings else "OK",
        "Ground-truth reviewed IP scope",
        (
            f"Missing ground-truth reviewed-IP source for ecosystems: {', '.join(reviewed_ip_warnings)}"
        )
        if reviewed_ip_warnings
        else "workbook or ips.csv present wherever ground-truth edges exist",
    )

    reviewed_ip_policy_warnings: list[str] = []
    for eco_slug, eco in sorted(ECOSYSTEM_REGISTRY.items()):
        if not eco.get("sources"):
            continue
        if not reviewed_ip_policy_for_ecosystem(eco_slug):
            continue
        reviewed_validation = validate_ground_truth_ips_file(
            eco_slug, ecosystem_config=eco
        )
        if reviewed_validation.warnings:
            reviewed_ip_policy_warnings.append(
                f"{eco_slug}: {reviewed_validation.warnings[0]}"
            )
    ok &= _doctor_row(
        table,
        "WARN" if reviewed_ip_policy_warnings else "OK",
        "Ground-truth sampling policy",
        "; ".join(reviewed_ip_policy_warnings)
        if reviewed_ip_policy_warnings
        else "reviewed IP sets match declared sampling policy",
    )

    validate_script = Path("scripts/validate_artifacts.py")
    if validate_script.exists():
        result = subprocess.run(
            [sys.executable, str(validate_script)],
            capture_output=True,
            text=True,
            check=False,
        )
        ok &= _doctor_row(
            table,
            "OK" if result.returncode == 0 else "FAIL",
            "Snapshot artifacts",
            "validation passed"
            if result.returncode == 0
            else "validation failed; run `python3 scripts/validate_artifacts.py`",
        )
    else:
        ok &= _doctor_row(
            table,
            "WARN",
            "Snapshot artifacts",
            "scripts/validate_artifacts.py not found",
        )

    generated_files = [
        Path("react/src/generated/ecosystems.json"),
        Path("react/src/generated/snapshotIndex.json"),
        Path("react/src/generated/proposalLinkIndex.json"),
    ]
    missing_generated = [str(path) for path in generated_files if not path.exists()]
    ok &= _doctor_row(
        table,
        "WARN" if missing_generated else "OK",
        "React generated assets",
        f"Missing: {', '.join(missing_generated)}; run `cd react && npm run prebuild`"
        if missing_generated
        else "generated indexes present",
    )

    api_key_present = (
        bool(os.getenv("OPENAI_API_KEY")) or Path("apikey.secret").exists()
    )
    ok &= _doctor_row(
        table,
        "OK" if api_key_present else "WARN",
        "OpenAI key",
        "available for LLM extraction"
        if api_key_present
        else "not set; `run --skipllm` still works",
    )

    console.print(table)
    if ok:
        console.print("[green]Doctor completed: no blocking issues found.[/green]")
        return

    console.print("[red]Doctor found blocking issues.[/red]")
    raise typer.Exit(1)
