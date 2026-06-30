"""CDV Explorer - comprehend and navigate your community-driven variability (CDV) exhibiting software ecosystem."""

from __future__ import annotations

import os
import sys

import json
import re
import shutil
import subprocess
import time
from datetime import date
from importlib import metadata
from pathlib import Path
from typing import Annotated, Optional

import typer
import yaml
from rich.console import Console
from rich.table import Table
from tqdm import tqdm

from analysis.proposal_schema import is_llm_runs_format, is_successful_llm_run
from ecosystems import ECOSYSTEM_REGISTRY
from pipeline.source_context import SourceContext

ECOSYSTEMS_DIR = Path(__file__).parent / "ecosystems"
console = Console()

app = typer.Typer(
    name="cdv-explorer",
    help=(
        "[bold]CDV Explorer[/bold] - comprehend and navigate your community-driven variability (CDV) exhibiting software ecosystem.\n\n"
        "Runs the full pipeline from harvesting raw IP documents to producing "
        "analysis artifacts consumed by the web UI. Ecosystems and their IP sources "
        "are declared in [cyan]ecosystems/*.yml[/cyan] - no code changes needed."
    ),
    rich_markup_mode="rich",
    add_completion=False,
    no_args_is_help=True,
    epilog=(
        "[bold]Examples[/bold]\n\n"
        "[green]python main.py run -e bitcoin -s 2026-03-16 --skipllm[/green]\n\n"
        "[green]python main.py run -e nostr -s 2026-03-16 --skipllm[/green]\n\n"
        "[green]python main.py snapshots[/green]\n\n"
        "[green]python main.py artifacts rebuild -e bitcoin -s 2026-03-16[/green]\n\n"
        "[green]python main.py artifacts rebuild -e bitcoin --all[/green]\n\n"
        "[green]python main.py doctor[/green]\n\n"
        "[green]python main.py ecosystems list[/green]\n\n"
        "[green]python main.py ecosystems show bitcoin[/green]\n\n"
        "[green]python main.py ecosystems add[/green]  "
        "[dim]# scaffold a new ecosystem YAML[/dim]\n\n"
        "[green]python main.py ecosystems add-source bitcoin[/green]  "
        "[dim]# add a second IP catalog[/dim]"
    ),
)
eco_app = typer.Typer(
    help="List, inspect, and scaffold ecosystem configs ([cyan]ecosystems/*.yml[/cyan]).",
    rich_markup_mode="rich",
    add_completion=False,
    no_args_is_help=True,
)
app.add_typer(eco_app, name="ecosystems", rich_help_panel="Discovery")
snapshots_app = typer.Typer(
    help="List and remove generated snapshot artifacts.",
    rich_markup_mode="rich",
    invoke_without_command=True,
)
app.add_typer(snapshots_app, name="snapshots", rich_help_panel="Discovery")
artifacts_app = typer.Typer(
    help="Rebuild generated analysis and postprocess artifacts from preprocessed JSON.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)
app.add_typer(artifacts_app, name="artifacts", rich_help_panel="Pipeline")
ground_truth_app = typer.Typer(
    help="Manage human-curated ground-truth benchmark files.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)
app.add_typer(ground_truth_app, name="ground-truth", rich_help_panel="Pipeline")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_ecosystem(slug: str) -> dict:
    eco = ECOSYSTEM_REGISTRY.get(slug)
    if eco is None:
        available = ", ".join(sorted(ECOSYSTEM_REGISTRY.keys()))
        console.print(f"[red]Unknown ecosystem '{slug}'. Available: {available}[/red]")
        raise typer.Exit(1)
    return eco


def _get_source(eco: dict, source_slug: str) -> dict:
    src = eco.get("sources", {}).get(source_slug)
    if src is None:
        available = ", ".join(sorted(eco.get("sources", {}).keys()))
        eco_slug = eco.get("slug", "?")
        console.print(
            f"[red]Unknown source '{source_slug}' in ecosystem '{eco_slug}'. "
            f"Available: {available}[/red]"
        )
        raise typer.Exit(1)
    return src


def _run_stage(name: str, total: int, unit: str, runner) -> None:
    progress = tqdm(
        total=max(total, 1),
        desc=name,
        unit=unit,
        dynamic_ncols=True,
        file=sys.stdout,
        leave=True,
    )

    def _update(message: str | None = None, advance: int = 0) -> None:
        if message:
            progress.set_postfix_str(message)
        if advance:
            progress.update(advance)

    try:
        runner(_update)
    finally:
        if progress.n < progress.total:
            progress.update(progress.total - progress.n)
        progress.close()


def _build_file_manifest(harvest_root: Path, src: dict) -> dict:
    prefix = src["document_prefix"]
    file_pattern = re.compile(src["document_file_pattern"], re.IGNORECASE)
    files: dict[str, str] = {}
    for p in harvest_root.iterdir():
        if not file_pattern.match(p.name):
            continue
        stem = p.stem
        id_part = (
            stem[len(prefix) + 1 :] if stem.lower().startswith(f"{prefix}-") else stem
        )
        try:
            id_key = str(int(id_part))
        except ValueError:
            id_key = id_part.upper()
        files[id_key] = p.name
    return files


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


def _prompt_choice(label: str, options: list[str], *, default_index: int = 0) -> str:
    if not options:
        raise typer.Exit(1)
    console.print(f"[bold]{label}[/bold]")
    for index, option in enumerate(options, start=1):
        marker = " [dim](default)[/dim]" if index - 1 == default_index else ""
        console.print(f"  {index}. {option}{marker}")
    while True:
        raw = typer.prompt("Choose a number", default=str(default_index + 1)).strip()
        try:
            selected = int(raw)
        except ValueError:
            console.print("[red]Please enter a number.[/red]")
            continue
        if 1 <= selected <= len(options):
            return options[selected - 1]
        console.print(f"[red]Please choose a value between 1 and {len(options)}.[/red]")


def _density_basis_description(value: str) -> str:
    descriptions = {
        "all_methods": "union of outgoing preamble, regex, and LLM relations",
        "regex_only": "outgoing regex relations only",
        "llm_only": "outgoing LLM relations only",
        "preamble_only": "outgoing preamble relations only",
    }
    return descriptions.get(value, value)


def _latest_snapshot_labels(analysis_root: Path) -> list[str]:
    if not analysis_root.is_dir():
        return []
    return sorted(
        (
            p.name
            for p in analysis_root.iterdir()
            if p.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", p.name)
        ),
        reverse=True,
    )


def _snapshot_labels(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    return sorted(
        (
            p.name
            for p in root.iterdir()
            if p.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", p.name)
        ),
    )


def _analysis_snapshot_labels_with_networks(analysis_root: Path) -> list[str]:
    labels: list[str] = []
    for snapshot in _snapshot_labels(analysis_root):
        network_path = analysis_root / snapshot / "dependencies" / "network_data.json"
        if network_path.exists():
            labels.append(snapshot)
    return labels


def _common_preprocess_snapshot_labels(sources: dict[str, dict]) -> list[str]:
    snapshot_sets = [
        set(_snapshot_labels(Path(src.get("preprocess", ""))))
        for src in sources.values()
    ]
    if not snapshot_sets:
        return []
    return sorted(set.intersection(*snapshot_sets))


def _snapshot_artifact_dirs(src: dict, snapshot: str) -> list[Path]:
    return [
        Path(src["preprocess"]) / snapshot,
        Path(src["analysis"]) / snapshot,
        Path(src["postprocess"]) / snapshot,
    ]


def _collect_snapshot_removal_targets(
    eco_slug: str,
    eco: dict,
    source_slug: str | None,
    snapshot: str,
) -> list[tuple[str, Path]]:
    sources: dict = eco.get("sources", {})
    selected_sources = (
        {source_slug: _get_source(eco, source_slug)} if source_slug else sources
    )
    targets: list[tuple[str, Path]] = []

    for src_slug, src in selected_sources.items():
        for artifact_dir in _snapshot_artifact_dirs(src, snapshot):
            if artifact_dir.exists():
                targets.append((src_slug, artifact_dir))

    return sorted(targets, key=lambda item: (item[0], str(item[1])))


def _remove_snapshot_targets(targets: list[tuple[str, Path]]) -> None:
    for _source_slug, target in targets:
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()


def _validate_snapshot_date(snapshot: str) -> None:
    try:
        date.fromisoformat(snapshot)
    except ValueError:
        console.print(f"[red]Invalid snapshot date '{snapshot}'. Use YYYY-MM-DD.[/red]")
        raise typer.Exit(1)


def _rebuild_source_artifacts(
    eco_slug: str,
    src_slug: str,
    src: dict,
    snapshot: str,
    *,
    artifact_llm_model: str | None = None,
    stage_label: str = "Build analysis and postprocess artifacts",
) -> None:
    """Rebuild analysis/postprocess artifacts for one source from existing preprocess JSON."""
    from analysis.pipeline import prepare_ecosystem_artifacts
    from analysis.validation import (
        sync_ground_truth_csvs_from_workbook,
        validate_ground_truth_curated_file,
        validate_ground_truth_ips_file,
        validate_source_snapshot,
    )

    harvest_root = Path(src["harvest"])
    preprocess_dir = Path(src["preprocess"]) / snapshot
    analysis_root = Path(src["analysis"])
    postprocess_root = Path(src["postprocess"])
    source_context = SourceContext.from_config(
        src, ecosystem_slug=eco_slug, source_slug=src_slug
    )

    if not preprocess_dir.is_dir():
        console.print(
            f"[red]Missing preprocessed JSON directory for {eco_slug}/{src_slug}: "
            f"{preprocess_dir}[/red]"
        )
        raise typer.Exit(1)

    if not any(preprocess_dir.glob("*.json")):
        console.print(
            f"[red]No preprocessed JSON files found for {eco_slug}/{src_slug}: "
            f"{preprocess_dir}[/red]"
        )
        raise typer.Exit(1)

    sync_ground_truth_csvs_from_workbook(eco_slug)

    resolved_artifact_llm_model = _resolve_artifact_llm_model(
        eco_slug=eco_slug,
        src_slug=src_slug,
        snapshot=snapshot,
        preprocess_dir=preprocess_dir,
        requested_model=artifact_llm_model,
    )

    ground_truth_validation = validate_ground_truth_curated_file(
        eco_slug, _get_ecosystem(eco_slug)
    )
    reviewed_ips_validation = validate_ground_truth_ips_file(
        eco_slug, _get_ecosystem(eco_slug)
    )
    ground_truth_errors = (
        ground_truth_validation.errors + reviewed_ips_validation.errors
    )
    if not ground_truth_validation.ok or not reviewed_ips_validation.ok:
        console.print(f"[red]Ground-truth validation failed for {eco_slug}:[/red]")
        for error in ground_truth_errors[:20]:
            console.print(f"  [red]-[/red] {error}")
        if len(ground_truth_errors) > 20:
            console.print(
                f"  [red]-[/red] ... and {len(ground_truth_errors) - 20} more"
            )
        raise typer.Exit(1)

    _run_stage(
        stage_label,
        9,
        "step",
        lambda u: prepare_ecosystem_artifacts(
            proposal_json_dir=preprocess_dir,
            artifact_root=analysis_root,
            postprocess_root=postprocess_root,
            snapshot=snapshot,
            id_field=src["primary_id_field"],
            proposal_label=src["proposal_acronym"],
            repo_dir=harvest_root if harvest_root.exists() else None,
            file_prefix=src["document_prefix"],
            source_context=source_context,
            artifact_llm_model=resolved_artifact_llm_model,
            progress_callback=u,
        ),
    )

    validation = validate_source_snapshot(
        ecosystem_slug=eco_slug,
        source_slug=src_slug,
        source_config=src,
        ecosystem_config=_get_ecosystem(eco_slug),
        snapshot=snapshot,
    )
    if not validation.ok:
        console.print(
            f"[red]Snapshot validation failed for {eco_slug}/{src_slug}/{snapshot}:[/red]"
        )
        for error in validation.errors[:20]:
            console.print(f"  [red]-[/red] {error}")
        if len(validation.errors) > 20:
            console.print(f"  [red]-[/red] ... and {len(validation.errors) - 20} more")
        raise typer.Exit(1)


def _count_source_combinations(source_count: int) -> int:
    if source_count < 2:
        return 0
    return (2**source_count) - source_count - 1


def _rebuild_combined_source_artifacts(eco_slug: str, eco: dict, snapshot: str) -> None:
    """Rebuild precomputed artifacts for every multi-source combination."""
    from analysis.pipeline import prepare_combined_source_artifacts
    from analysis.validation import validate_combined_snapshot

    sources = eco.get("sources", {})
    combo_count = _count_source_combinations(len(sources))
    if combo_count == 0:
        return

    saved: dict[str, dict[str, Path]] = {}

    def _run(progress_callback) -> None:
        nonlocal saved
        saved = prepare_combined_source_artifacts(
            ecosystem_slug=eco_slug,
            source_configs=sources,
            snapshot=snapshot,
            progress_callback=progress_callback,
        )

    _run_stage(
        "Build combined source artifacts".ljust(28),
        combo_count * 6,
        "step",
        _run,
    )

    for combo_key in saved:
        validation = validate_combined_snapshot(
            ecosystem_slug=eco_slug, combo_key=combo_key, snapshot=snapshot
        )
        if not validation.ok:
            console.print(
                f"[red]Snapshot validation failed for {eco_slug}/{combo_key}/{snapshot}:[/red]"
            )
            for error in validation.errors[:20]:
                console.print(f"  [red]-[/red] {error}")
            if len(validation.errors) > 20:
                console.print(
                    f"  [red]-[/red] ... and {len(validation.errors) - 20} more"
                )
            raise typer.Exit(1)


def _rebuild_artifacts_for_targets(
    eco_slug: str,
    eco: dict,
    targets: dict[str, dict],
    snapshot: str,
    *,
    artifact_llm_model: str | None = None,
) -> None:
    if len(targets) == 1:
        src_slug, src_cfg = next(iter(targets.items()))
        _rebuild_source_artifacts(
            eco_slug, src_slug, src_cfg, snapshot, artifact_llm_model=artifact_llm_model
        )
        return

    resolved_models_by_source = {
        src_slug: _resolve_artifact_llm_model(
            eco_slug=eco_slug,
            src_slug=src_slug,
            snapshot=snapshot,
            preprocess_dir=Path(src_cfg["preprocess"]) / snapshot,
            requested_model=artifact_llm_model,
        )
        for src_slug, src_cfg in targets.items()
    }
    distinct_models = sorted(
        {model for model in resolved_models_by_source.values() if model}
    )
    if len(distinct_models) > 1:
        model_lines = ", ".join(
            f"{src_slug}={model}"
            for src_slug, model in sorted(resolved_models_by_source.items())
            if model
        )
        console.print(
            f"[red]Selected sources would publish different LLM models for {eco_slug}/{snapshot}: "
            f"{model_lines}[/red]"
        )
        console.print(
            "[yellow]Re-run with `--artifact-llm-model <model>` after ensuring that model exists in every selected source.[/yellow]"
        )
        raise typer.Exit(1)

    for src_slug, src_cfg in targets.items():
        console.rule(f"[bold]{eco_slug} / {src_slug}[/bold]")
        _rebuild_source_artifacts(
            eco_slug, src_slug, src_cfg, snapshot, artifact_llm_model=artifact_llm_model
        )
    _rebuild_combined_source_artifacts(eco_slug, eco, snapshot)


def _analysis_dirs_for_ecosystem(
    eco_dir: Path, eco_config: dict | None = None
) -> list[tuple[str | None, Path]]:
    direct = eco_dir / "03_analysis"
    if direct.is_dir():
        matched_source = None
        for source_slug, source in sorted(
            (eco_config or {}).get("sources", {}).items()
        ):
            if Path(source.get("analysis", "")) == direct:
                matched_source = source_slug
                break
        return [(matched_source, direct)]

    source_dirs = [
        (source_dir.name, source_dir / "03_analysis")
        for source_dir in sorted(eco_dir.iterdir())
        if source_dir.is_dir()
        and source_dir.name != "_combined"
        and (source_dir / "03_analysis").is_dir()
    ]
    combined_root = eco_dir / "_combined"
    combo_dirs = (
        [
            (combo_dir.name, combo_dir / "03_analysis")
            for combo_dir in sorted(combined_root.iterdir())
            if combined_root.is_dir()
            and combo_dir.is_dir()
            and (combo_dir / "03_analysis").is_dir()
        ]
        if combined_root.is_dir()
        else []
    )
    return source_dirs + combo_dirs


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


def _parse_focus(focus_str: str | None) -> set[str] | None:
    """Parse '1-9,30-44,85,A0' into a set of normalized ID strings."""
    if not focus_str:
        return None
    ids: set[str] = set()
    for part in focus_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, _, hi = part.partition("-")
            try:
                for i in range(int(lo.strip()), int(hi.strip()) + 1):
                    ids.add(str(i))
                continue
            except ValueError:
                # Non-numeric ranges like "A0-A3" are treated as literal IDs below.
                pass
        ids.add(part)
        ids.add(part.upper())
    return ids or None


def _existing_llm_model_run_counts(
    preprocess_dir: Path,
    *,
    id_field: str,
    llm_model: str,
    focus: set[str] | None = None,
) -> tuple[int, int]:
    matching_documents = 0
    matching_runs = 0

    for json_file in sorted(preprocess_dir.glob("*.json")):
        raw_json = json.loads(json_file.read_text(encoding="utf-8"))
        preamble = raw_json.get("raw", {}).get("preamble", {})
        raw_id = str(preamble.get(id_field, ""))
        try:
            proposal_number = str(int(raw_id))
        except ValueError:
            proposal_number = raw_id
        if focus is not None:
            in_focus = (
                proposal_number in focus
                or raw_id in focus
                or proposal_number.upper() in focus
                or raw_id.upper() in focus
            )
            if not in_focus:
                continue

        raw_llm = (
            raw_json.get("insights", {})
            .get("interrelations", {})
            .get("body_extracted_llm", [])
        )
        if not is_llm_runs_format(raw_llm):
            continue

        doc_counted = False
        for run in raw_llm:
            if str(run.get("model") or "").strip() != llm_model:
                continue
            matching_runs += 1
            if not doc_counted:
                matching_documents += 1
                doc_counted = True

    return matching_documents, matching_runs


def _failed_llm_model_focus(
    preprocess_dir: Path,
    *,
    id_field: str,
    llm_model: str,
    focus: set[str] | None = None,
) -> set[str]:
    failed_ids: set[str] = set()

    for json_file in sorted(preprocess_dir.glob("*.json")):
        raw_json = json.loads(json_file.read_text(encoding="utf-8"))
        preamble = raw_json.get("raw", {}).get("preamble", {})
        raw_id = str(preamble.get(id_field, ""))
        try:
            proposal_number = str(int(raw_id))
        except ValueError:
            proposal_number = raw_id
        if focus is not None:
            in_focus = (
                proposal_number in focus
                or raw_id in focus
                or proposal_number.upper() in focus
                or raw_id.upper() in focus
            )
            if not in_focus:
                continue

        raw_llm = (
            raw_json.get("insights", {})
            .get("interrelations", {})
            .get("body_extracted_llm", [])
        )
        if not is_llm_runs_format(raw_llm):
            continue

        model_runs = [
            run
            for run in raw_llm
            if str(run.get("model") or "").strip() == llm_model
        ]
        if not model_runs:
            continue

        latest_run = max(model_runs, key=lambda run: str(run.get("timestamp") or ""))
        if is_successful_llm_run(latest_run):
            continue

        failed_ids.add(proposal_number)

    return failed_ids


def _available_llm_models_in_preprocess_dir(preprocess_dir: Path) -> list[str]:
    models: set[str] = set()
    for json_file in sorted(preprocess_dir.glob("*.json")):
        raw_json = json.loads(json_file.read_text(encoding="utf-8"))
        raw_llm = (
            raw_json.get("insights", {})
            .get("interrelations", {})
            .get("body_extracted_llm", [])
        )
        if not is_llm_runs_format(raw_llm):
            continue
        for run in raw_llm:
            model = str(run.get("model") or "").strip()
            if model and is_successful_llm_run(run):
                models.add(model)
    return sorted(models)


def _resolve_artifact_llm_model(
    *,
    eco_slug: str,
    src_slug: str,
    snapshot: str,
    preprocess_dir: Path,
    requested_model: str | None,
) -> str | None:
    available_models = _available_llm_models_in_preprocess_dir(preprocess_dir)
    requested = str(requested_model or "").strip()

    if requested:
        if requested not in available_models:
            console.print(
                f"[red]Requested artifact LLM model '{requested}' is not available for "
                f"{eco_slug}/{src_slug}/{snapshot}. Available models: "
                f"{', '.join(available_models) if available_models else '(none)'}[/red]"
            )
            raise typer.Exit(1)
        return requested

    if len(available_models) <= 1:
        return available_models[0] if available_models else None

    console.print(
        f"[red]Multiple LLM models are present for {eco_slug}/{src_slug}/{snapshot}: "
        f"{', '.join(available_models)}[/red]"
    )
    console.print(
        "[yellow]Choose which model should be published into the web artifacts with "
        "`--artifact-llm-model <model>`.[/yellow]"
    )
    raise typer.Exit(1)


def _run_source_pipeline(
    eco_slug: str,
    src_slug: str,
    src: dict,
    snapshot: str,
    skipllm: bool,
    focus: set[str] | None = None,
    rerun_failed_only: bool = False,
    artifact_llm_model: str | None = None,
) -> None:
    """Run the full pipeline for one source."""
    from pipeline.harvest import get_harvester
    from pipeline.preprocess import get_extractor, get_enricher

    harvest_root = Path(src["harvest"])
    preprocess_root = Path(src["preprocess"])
    analysis_root = Path(src["analysis"])
    output_dir = preprocess_root / snapshot
    prefix = src["document_prefix"]
    source_context = SourceContext.from_config(
        src, ecosystem_slug=eco_slug, source_slug=src_slug
    )

    harvester = get_harvester(src.get("harvester", "github_repo"))
    extractor = get_extractor(src.get("preprocessor", "rfc_preamble"))
    enricher = get_enricher()

    _run_stage(
        "Step 1/4 · I. Harvest".ljust(28),
        3,
        "step",
        lambda u: harvester(
            src_config=src,
            snapshot=snapshot,
            local_dir=harvest_root,
            progress_callback=u,
        ),
    )

    commit = subprocess.run(
        ["git", "-C", str(harvest_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    manifest = {
        "commit": commit,
        "files": _build_file_manifest(harvest_root, src),
    }
    manifest_path = analysis_root / snapshot / f"{prefix}_files.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )

    effective_focus = focus
    if rerun_failed_only:
        if skipllm or not source_context.llm_model:
            console.print(
                f"[yellow]Skipping failed-only rerun for {eco_slug}/{src_slug}/{snapshot} because LLM extraction is not enabled.[/yellow]"
            )
            return
        if not output_dir.exists():
            console.print(
                f"[yellow]Skipping failed-only rerun for {eco_slug}/{src_slug}/{snapshot} because no preprocess snapshot exists yet.[/yellow]"
            )
            return
        failed_focus = _failed_llm_model_focus(
            output_dir,
            id_field=src["primary_id_field"],
            llm_model=str(source_context.llm_model or "").strip(),
            focus=focus,
        )
        if not failed_focus:
            console.print(
                f"[yellow]No failed LLM runs found for {eco_slug}/{src_slug}/{snapshot}.[/yellow]"
            )
            return
        effective_focus = failed_focus
        console.print(
            f"[yellow]Re-running failed LLM rows only for {eco_slug}/{src_slug}/{snapshot}: "
            f"{len(failed_focus)} IP(s) matched.[/yellow]"
        )

    preprocess_exists = output_dir.exists() and any(output_dir.glob("*.json"))
    if effective_focus is not None and preprocess_exists:
        console.print(
            f"  [green]✓[/green]  {'Step 2/4 · II. Preprocess'.ljust(28)}  [dim]skipped — focus run, existing preambles preserved[/dim]"
        )
    else:
        file_pattern = re.compile(src["document_file_pattern"], re.IGNORECASE)
        proposal_files = [
            p for p in harvest_root.iterdir() if file_pattern.match(p.name)
        ]
        _run_stage(
            "Step 2/4 · II. Preprocess".ljust(28),
            len(proposal_files),
            "ip",
            lambda u: extractor(
                src_config=src,
                harvest_dir=harvest_root,
                output_dir=output_dir,
                progress_callback=u,
            ),
        )

    json_files = list(output_dir.glob("*.json")) if output_dir.exists() else []
    replace_llm_model_runs = False
    if not skipllm and source_context.llm_model and output_dir.exists() and not rerun_failed_only:
        matching_docs, matching_runs = _existing_llm_model_run_counts(
            output_dir,
            id_field=src["primary_id_field"],
            llm_model=source_context.llm_model,
            focus=effective_focus,
        )
        if matching_runs:
            focus_scope = (
                f" among {matching_docs} focused IPs"
                if effective_focus is not None
                else f" in {matching_docs} IPs"
            )
            console.print(
                f"[yellow]LLM model '{source_context.llm_model}' already has {matching_runs} stored run(s){focus_scope} "
                f"for {eco_slug}/{src_slug}/{snapshot}. Re-running will replace those same-model records and keep runs from other models.[/yellow]"
            )
            if not typer.confirm(
                "Proceed and overwrite same-model LLM runs?", default=True
            ):
                raise typer.Exit(1)
            replace_llm_model_runs = True

    focus_note = (
        f"  (focus: {len(effective_focus)}/{len(json_files)} ip)"
        if effective_focus
        else ""
    )
    _run_stage(
        f"{'Step 3/4 · III. Analysis'.ljust(28)}{focus_note}",
        len(json_files),
        "ip",
        lambda u: enricher(
            src_config=src,
            preprocess_dir=output_dir,
            harvest_dir=harvest_root,
            analysis_snapshot_dir=analysis_root / snapshot,
            skip_llm=skipllm,
            focus=effective_focus,
            replace_llm_model_runs=replace_llm_model_runs,
            source_context=source_context,
            progress_callback=u,
        ),
    )

    _rebuild_source_artifacts(
        eco_slug,
        src_slug,
        src,
        snapshot,
        artifact_llm_model=artifact_llm_model,
        stage_label="Step 4/4 · IV. Postprocess".ljust(28),
    )


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


@app.command(rich_help_panel="Discovery")
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


@app.command(rich_help_panel="Pipeline")
def run(
    ecosystem: Annotated[
        Optional[str],
        typer.Option(
            "--ecosystem", "-e", help="Ecosystem slug (default: first registered)."
        ),
    ] = None,
    source: Annotated[
        Optional[str],
        typer.Option("--source", help="Source slug (default: all sources)."),
    ] = None,
    snapshot: Annotated[
        str,
        typer.Option("--snapshot", "-s", help="Snapshot date (YYYY-MM-DD). Required."),
    ] = ...,
    skipllm: Annotated[
        bool, typer.Option("--skipllm", help="Skip LLM-based extraction.")
    ] = False,
    focus: Annotated[
        Optional[str],
        typer.Option(
            "--focus",
            help="Comma-separated list of proposal IDs to process (e.g. '1-9,30-44,85,A0'). All others are skipped.",
        ),
    ] = None,
    rerun_failed_only: Annotated[
        bool,
        typer.Option(
            "--rerun-failed-only",
            help="Only re-run LLM extraction for rows whose latest stored LLM run failed.",
        ),
    ] = False,
    artifact_llm_model: Annotated[
        Optional[str],
        typer.Option(
            "--artifact-llm-model",
            help="LLM model to publish into web artifacts when multiple stored LLM runs exist.",
        ),
    ] = None,
) -> None:
    """Run the full pipeline for a snapshot. Runs all sources unless --source is given."""
    eco_slug = ecosystem or next(iter(ECOSYSTEM_REGISTRY), None)
    if not eco_slug:
        console.print(
            "[red]No ecosystems registered. Add a .yml file to the ecosystems/ directory.[/red]"
        )
        raise typer.Exit(1)
    eco = _get_ecosystem(eco_slug)

    _validate_snapshot_date(snapshot)

    sources: dict = eco.get("sources", {})
    if not sources:
        console.print(f"[red]Ecosystem '{eco_slug}' has no sources configured.[/red]")
        raise typer.Exit(1)

    focus_ids = _parse_focus(focus)

    targets: dict[str, dict] = {source: _get_source(eco, source)} if source else sources

    if len(targets) == 1:
        src_slug, src_cfg = next(iter(targets.items()))
        run_started = time.monotonic()
        _run_source_pipeline(
            eco_slug,
            src_slug,
            src_cfg,
            snapshot,
            skipllm,
            focus_ids,
            rerun_failed_only,
            artifact_llm_model,
        )
        elapsed = time.monotonic() - run_started
        console.print(f"\n[green]Done in {elapsed:.1f}s[/green]")
    else:
        run_started = time.monotonic()
        for src_slug, src_cfg in targets.items():
            console.rule(f"[bold]{eco_slug} / {src_slug}[/bold]")
            _run_source_pipeline(
                eco_slug,
                src_slug,
                src_cfg,
                snapshot,
                skipllm,
                focus_ids,
                rerun_failed_only,
                artifact_llm_model,
            )
        _rebuild_combined_source_artifacts(eco_slug, eco, snapshot)
        elapsed = time.monotonic() - run_started
        console.print(f"\n[green]All sources done in {elapsed:.1f}s[/green]")


# ---------------------------------------------------------------------------
# artifacts
# ---------------------------------------------------------------------------


@artifacts_app.command("rebuild", rich_help_panel="Manage")
def artifacts_rebuild(
    ecosystem: Annotated[
        Optional[str],
        typer.Option(
            "--ecosystem", "-e", help="Ecosystem slug (default: first registered)."
        ),
    ] = None,
    source: Annotated[
        Optional[str],
        typer.Option("--source", help="Source slug (default: all sources)."),
    ] = None,
    snapshot: Annotated[
        Optional[str],
        typer.Option(
            "--snapshot",
            "-s",
            help="Snapshot date (YYYY-MM-DD). Required unless --all is used.",
        ),
    ] = None,
    all_snapshots: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Rebuild every existing preprocessed snapshot for the selected ecosystem/source.",
        ),
    ] = False,
    artifact_llm_model: Annotated[
        Optional[str],
        typer.Option(
            "--artifact-llm-model",
            help="LLM model to publish into web artifacts when multiple stored LLM runs exist.",
        ),
    ] = None,
) -> None:
    """Rebuild analysis and postprocess artifacts from existing preprocessed JSON."""
    eco_slug = ecosystem or next(iter(ECOSYSTEM_REGISTRY), None)
    if not eco_slug:
        console.print(
            "[red]No ecosystems registered. Add a .yml file to the ecosystems/ directory.[/red]"
        )
        raise typer.Exit(1)
    eco = _get_ecosystem(eco_slug)
    if all_snapshots and snapshot:
        console.print("[red]Use either --all or --snapshot, not both.[/red]")
        raise typer.Exit(1)
    if not all_snapshots and not snapshot:
        console.print(
            "[red]Missing option '--snapshot' / '-s'. Use --all to rebuild every preprocessed snapshot.[/red]"
        )
        raise typer.Exit(1)
    if snapshot:
        _validate_snapshot_date(snapshot)

    sources: dict = eco.get("sources", {})
    if not sources:
        console.print(f"[red]Ecosystem '{eco_slug}' has no sources configured.[/red]")
        raise typer.Exit(1)

    targets: dict[str, dict] = {source: _get_source(eco, source)} if source else sources

    rebuild_started = time.monotonic()

    if all_snapshots:
        snapshots = _common_preprocess_snapshot_labels(targets)
        if not snapshots:
            scope = f"{eco_slug}/{source}" if source else eco_slug
            console.print(
                f"[yellow]No preprocessed snapshots found for {scope}.[/yellow]"
            )
            raise typer.Exit(0)

        for snapshot_label in snapshots:
            console.rule(f"[bold]{eco_slug} / {snapshot_label}[/bold]")
            _rebuild_artifacts_for_targets(
                eco_slug,
                eco,
                targets,
                snapshot_label,
                artifact_llm_model=artifact_llm_model,
            )
        elapsed = time.monotonic() - rebuild_started
        console.print(
            f"\n[green]Artifacts rebuilt for {len(snapshots)} snapshot(s) in {elapsed:.1f}s[/green]"
        )
        return

    _rebuild_artifacts_for_targets(
        eco_slug,
        eco,
        targets,
        snapshot,
        artifact_llm_model=artifact_llm_model,
    )
    elapsed = time.monotonic() - rebuild_started
    if len(targets) == 1:
        console.print(f"\n[green]Artifacts rebuilt in {elapsed:.1f}s[/green]")
    else:
        console.print(
            f"\n[green]Artifacts rebuilt for all sources in {elapsed:.1f}s[/green]"
        )


# ---------------------------------------------------------------------------
# ground-truth
# ---------------------------------------------------------------------------


@ground_truth_app.command("sample-ips", rich_help_panel="Manage")
def ground_truth_sample_ips(
    ecosystem: Annotated[
        Optional[str], typer.Option("--ecosystem", "-e", help="Ecosystem slug.")
    ] = None,
    source: Annotated[
        Optional[str], typer.Option("--source", help="Source slug to sample from.")
    ] = None,
    snapshot: Annotated[
        Optional[str],
        typer.Option("--snapshot", "-s", help="Snapshot date (YYYY-MM-DD)."),
    ] = None,
    count: Annotated[
        Optional[int],
        typer.Option("--count", help="Number of new reviewed IP rows to prefill."),
    ] = None,
    seed: Annotated[
        Optional[int],
        typer.Option(
            "--seed", help="Random seed for reproducible stratified sampling."
        ),
    ] = None,
    era_buckets: Annotated[
        Optional[int],
        typer.Option(
            "--era-buckets", min=1, help="Number of time-based strata to use."
        ),
    ] = None,
    density_basis: Annotated[
        Optional[str],
        typer.Option(
            "--density-basis",
            help="Density basis: all_methods, regex_only, llm_only, or preamble_only.",
        ),
    ] = None,
    density_low_max: Annotated[
        Optional[int],
        typer.Option(
            "--density-low-max",
            min=0,
            help="Upper bound for the `low` extracted-density bucket; values above this become `high`.",
        ),
    ] = None,
    proposal_type: Annotated[
        Optional[str],
        typer.Option(
            "--proposal-type",
            help="Optional exact proposal type filter (e.g. Specification).",
        ),
    ] = None,
    reviewer: Annotated[
        Optional[str],
        typer.Option(
            "--reviewer", help="Optional reviewer name to prefill in new rows."
        ),
    ] = None,
    replace: Annotated[
        Optional[bool],
        typer.Option(
            "--replace/--append", help="Overwrite ips.csv or append new rows."
        ),
    ] = None,
    wizard: Annotated[
        bool, typer.Option("--wizard", help="Force interactive step-by-step prompts.")
    ] = False,
) -> None:
    """Prefill ground_truth/ips.csv from a stratified source-IP sample."""
    from analysis.ground_truth_sampling import (
        ALL_METHODS,
        DENSITY_BASIS_OPTIONS,
        LLM_ONLY,
        PREAMBLE_ONLY,
        REGEX_ONLY,
        prefill_ips_csv,
    )
    from analysis.validation import (
        reviewed_ip_policy_for_ecosystem,
        validate_ground_truth_ips_file,
    )

    interactive = wizard or ecosystem is None or source is None or snapshot is None
    available_ecosystems = [
        slug for slug, eco in sorted(ECOSYSTEM_REGISTRY.items()) if eco.get("sources")
    ]
    if not available_ecosystems:
        console.print("[red]No ecosystems with configured sources are available.[/red]")
        raise typer.Exit(1)

    if ecosystem is None:
        ecosystem = _prompt_choice("Ecosystem", available_ecosystems)
    eco = _get_ecosystem(ecosystem)

    available_sources = sorted(eco.get("sources", {}).keys())
    if source is None:
        source = _prompt_choice("Source", available_sources)
    src = _get_source(eco, source)
    reviewed_ip_policy = reviewed_ip_policy_for_ecosystem(ecosystem)

    available_snapshots = _analysis_snapshot_labels_with_networks(
        Path(str(src["analysis"]))
    )
    if not available_snapshots:
        console.print(
            f"[red]No analysis snapshots with dependency network artifacts found for {ecosystem}/{source}.[/red]"
        )
        raise typer.Exit(1)
    if snapshot is None:
        snapshot = _prompt_choice("Snapshot", list(reversed(available_snapshots)))
    _validate_snapshot_date(snapshot)

    if count is None:
        count = (
            int(
                typer.prompt("How many new reviewed IPs should be added?", default="30")
            )
            if interactive
            else 30
        )
    if count < 1:
        console.print("[red]`--count` must be at least 1.[/red]")
        raise typer.Exit(1)

    if seed is None:
        seed = int(typer.prompt("Random seed", default="42")) if interactive else 42
    if era_buckets is None:
        era_buckets = (
            int(typer.prompt("Number of era buckets", default="3"))
            if interactive
            else 3
        )
    if density_basis is None:
        if interactive:
            basis_label = _prompt_choice(
                "Density basis",
                [
                    f"{ALL_METHODS} (union of preamble, regex, and LLM outgoing targets)",
                    f"{REGEX_ONLY} (regex outgoing targets only)",
                    f"{LLM_ONLY} (LLM outgoing targets only)",
                    f"{PREAMBLE_ONLY} (preamble outgoing targets only)",
                ],
            )
            density_basis = basis_label.split(" ", 1)[0]
        else:
            density_basis = ALL_METHODS
    if density_basis not in DENSITY_BASIS_OPTIONS:
        allowed = ", ".join(sorted(DENSITY_BASIS_OPTIONS))
        console.print(f"[red]Invalid `--density-basis`. Allowed: {allowed}[/red]")
        raise typer.Exit(1)
    if density_low_max is None:
        density_low_max = (
            int(
                typer.prompt(
                    "Largest extracted-target count still treated as `low` density",
                    default="2",
                )
            )
            if interactive
            else 2
        )
    if proposal_type is None:
        default_proposal_type = ""
        if reviewed_ip_policy and source in set(
            reviewed_ip_policy.get("allowed_source_slugs", ())
        ):
            default_proposal_type = str(
                reviewed_ip_policy.get("required_type") or ""
            ).strip()
        proposal_type = (
            typer.prompt(
                "Restrict to proposal type (optional)",
                default=default_proposal_type,
            ).strip()
            if interactive
            else default_proposal_type
        )
    if reviewer is None:
        reviewer = (
            typer.prompt("Reviewer name to prefill (optional)", default="")
            if interactive
            else ""
        )
    if replace is None:
        if interactive:
            replace_choice = _prompt_choice(
                "Pending append workbook",
                ["append to ips_append.xlsx", "replace ips_append.xlsx"],
            )
            replace = replace_choice == "replace ips_append.xlsx"
        else:
            replace = False

    policy_warnings: list[str] = []
    if reviewed_ip_policy:
        allowed_source_slugs = {
            str(value).strip()
            for value in reviewed_ip_policy.get("allowed_source_slugs", ())
            if str(value).strip()
        }
        required_type = str(reviewed_ip_policy.get("required_type") or "").strip()
        if allowed_source_slugs and source not in allowed_source_slugs:
            policy_warnings.append(
                f"Current GT policy for `{ecosystem}` expects source `{', '.join(sorted(allowed_source_slugs))}`, but you selected `{source}`."
            )
        if (
            required_type
            and source in allowed_source_slugs
            and proposal_type != required_type
        ):
            selected_type = proposal_type or "no type filter"
            policy_warnings.append(
                f"Current GT policy for `{ecosystem}` expects proposal type `{required_type}`, but this run uses `{selected_type}`."
            )

    if interactive:
        console.print("")
        console.print("[bold]Sampling plan[/bold]")
        console.print(f"  Ecosystem: {ecosystem}")
        console.print(f"  Source: {source}")
        console.print(f"  Snapshot: {snapshot}")
        console.print(f"  Count: {count}")
        console.print(f"  Seed: {seed}")
        console.print(
            f"  Era buckets: {era_buckets}  [dim](created-date strata such as early/middle/recent)[/dim]"
        )
        console.print(
            f"  Density basis: {density_basis}  [dim]({_density_basis_description(density_basis)})[/dim]"
        )
        console.print(f"  Low-density max: {density_low_max}")
        console.print(f"  Proposal type filter: {proposal_type or '—'}")
        console.print(f"  Reviewer: {reviewer or '—'}")
        console.print(
            "  Pending append workbook: "
            + ("replace ips_append.xlsx" if replace else "append to ips_append.xlsx")
        )
        if reviewed_ip_policy:
            policy_bits = []
            if reviewed_ip_policy.get("allowed_source_slugs"):
                policy_bits.append(
                    f"source in {', '.join(reviewed_ip_policy['allowed_source_slugs'])}"
                )
            if reviewed_ip_policy.get("required_type"):
                policy_bits.append(f"type = {reviewed_ip_policy['required_type']}")
            console.print(f"  GT policy: {'; '.join(policy_bits)}")
        for warning in policy_warnings:
            console.print(f"  [yellow]Warning:[/yellow] {warning}")
        if not typer.confirm("Proceed?", default=True):
            raise typer.Exit(0)
    elif policy_warnings:
        for warning in policy_warnings:
            console.print(f"[yellow]Warning:[/yellow] {warning}")

    network_path = (
        Path(str(src["analysis"])) / snapshot / "dependencies" / "network_data.json"
    )
    if not network_path.exists():
        console.print(
            f"[red]Missing dependency network artifact for {ecosystem}/{source}/{snapshot}: "
            f"{network_path}[/red]"
        )
        console.print(
            f"[yellow]Rebuild artifacts first, e.g. `python main.py artifacts rebuild -e {ecosystem} --source {source} -s {snapshot}`[/yellow]"
        )
        raise typer.Exit(1)

    result = prefill_ips_csv(
        ecosystem,
        source_slug=source,
        network_path=network_path,
        count=count,
        seed=seed,
        era_bucket_count=era_buckets,
        density_basis=density_basis,
        density_low_max=density_low_max,
        proposal_type=proposal_type or None,
        reviewer=reviewer or "",
        replace=replace,
    )

    validation = validate_ground_truth_ips_file(ecosystem, ecosystem_config=eco)
    if not validation.ok:
        console.print(f"[red]Reviewed-IP validation failed for {ecosystem}:[/red]")
        for error in validation.errors[:20]:
            console.print(f"  [red]-[/red] {error}")
        if len(validation.errors) > 20:
            console.print(f"  [red]-[/red] ... and {len(validation.errors) - 20} more")
        raise typer.Exit(1)

    workbook_path = result.get("workbook_path")
    if workbook_path:
        console.print(f"[green]Updated[/green] {workbook_path}")
        console.print(
            "[dim]This is a pending append workbook. "
            "ground_truth.xlsx remains untouched. CSV sync is deferred to artifact rebuild.[/dim]"
        )
    console.print(
        f"Reviewed IPs in ground_truth.xlsx: {result.get('reviewed_count', 0)} | "
        f"Existing pending rows kept: {result['existing_count']} | "
        f"New rows added: {result['added_count']} | "
        f"Total pending rows: {result['total_count']}"
    )
    if result.get("proposal_type"):
        console.print(f"Type filter: {result['proposal_type']}")

    if result["sampled_rows"]:
        strata_table = Table("Stratum", "Count", title="Sample Composition")
        for stratum, sample_count in sorted(result["strata_counts"].items()):
            strata_table.add_row(stratum, str(sample_count))
        console.print(strata_table)
    else:
        console.print(
            "[yellow]No new IPs were added. The reviewed set already covers the available candidates.[/yellow]"
        )


# ---------------------------------------------------------------------------
# snapshots
# ---------------------------------------------------------------------------


def _print_snapshots(
    ecosystem: Annotated[
        Optional[str], typer.Option("--ecosystem", "-e", help="Filter by ecosystem.")
    ] = None,
) -> None:
    ip_root = Path("ip_data")
    if not ip_root.exists():
        console.print("[yellow]No ip_data directory found.[/yellow]")
        raise typer.Exit(0)

    table = Table(
        "Ecosystem", "Source", "Snapshot", "Path", title="Available Snapshots"
    )
    found = False

    for eco_dir in sorted(ip_root.iterdir()):
        if not eco_dir.is_dir():
            continue
        slug = eco_dir.name
        if ecosystem and slug != ecosystem:
            continue
        for source_slug, analysis_dir in _analysis_dirs_for_ecosystem(
            eco_dir, ECOSYSTEM_REGISTRY.get(slug)
        ):
            for snap_dir in sorted(analysis_dir.iterdir(), reverse=True):
                if snap_dir.is_dir():
                    table.add_row(
                        slug, source_slug or "—", snap_dir.name, str(snap_dir)
                    )
                    found = True

    if found:
        console.print(table)
    else:
        suffix = f" for ecosystem '{ecosystem}'" if ecosystem else ""
        console.print(f"[yellow]No snapshots found{suffix}.[/yellow]")


@snapshots_app.callback(invoke_without_command=True)
def snapshots(
    ctx: typer.Context,
    ecosystem: Annotated[
        Optional[str], typer.Option("--ecosystem", "-e", help="Filter by ecosystem.")
    ] = None,
) -> None:
    """List available snapshots found under ip_data/."""
    if ctx.invoked_subcommand is not None:
        return
    _print_snapshots(ecosystem=ecosystem)


@snapshots_app.command("list", rich_help_panel="Inspect")
def snapshots_list(
    ecosystem: Annotated[
        Optional[str], typer.Option("--ecosystem", "-e", help="Filter by ecosystem.")
    ] = None,
) -> None:
    """List available snapshots found under ip_data/."""
    _print_snapshots(ecosystem=ecosystem)


@snapshots_app.command("remove", rich_help_panel="Manage")
def snapshots_remove(
    snapshot: Annotated[
        str, typer.Argument(help="Snapshot date to remove (YYYY-MM-DD).")
    ],
    ecosystem: Annotated[
        str, typer.Option("--ecosystem", "-e", help="Ecosystem slug.")
    ],
    source: Annotated[
        Optional[str],
        typer.Option(
            "--source", help="Source slug. Omit to remove all sources in the ecosystem."
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Show matching snapshot directories without deleting."
        ),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes", "-y", help="Delete without an interactive confirmation prompt."
        ),
    ] = False,
) -> None:
    """Remove generated preprocess, analysis, and postprocess directories for a snapshot."""
    _validate_snapshot_date(snapshot)

    eco = _get_ecosystem(ecosystem)
    targets = _collect_snapshot_removal_targets(ecosystem, eco, source, snapshot)
    if not targets:
        scope = f"{ecosystem}/{source}" if source else ecosystem
        console.print(
            f"[yellow]No generated snapshot directories found for {scope} at {snapshot}.[/yellow]"
        )
        return

    table = Table("Source", "Path", title=f"Snapshot Removal: {ecosystem} / {snapshot}")
    for src_slug, target in targets:
        table.add_row(src_slug, str(target))
    console.print(table)

    if dry_run:
        console.print("[green]Dry run complete. No files were removed.[/green]")
        return

    if not yes:
        if not typer.confirm("Remove these generated snapshot directories?"):
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(1)

    _remove_snapshot_targets(targets)
    console.print(
        f"[green]Removed {len(targets)} generated snapshot director{'y' if len(targets) == 1 else 'ies'}.[/green]"
    )


# ---------------------------------------------------------------------------
# ecosystems
# ---------------------------------------------------------------------------


@eco_app.command("list", rich_help_panel="Inspect")
def ecosystems_list() -> None:
    """List all registered ecosystems."""
    table = Table("Slug", "Display name", "Sources", title="Registered Ecosystems")
    for slug, eco in sorted(ECOSYSTEM_REGISTRY.items()):
        sources = eco.get("sources", {})
        src_summary = ", ".join(
            f"{s} ({v.get('proposal_acronym', '?')})" for s, v in sources.items()
        )
        table.add_row(slug, eco.get("display_name", slug), src_summary or "—")
    console.print(table)


@eco_app.command("show", rich_help_panel="Inspect")
def ecosystems_show(
    slug: Annotated[str, typer.Argument(help="Ecosystem slug.")],
) -> None:
    """Print the full YAML config for an ecosystem."""
    eco = _get_ecosystem(slug)
    console.print_json(json.dumps(eco, indent=2))


@eco_app.command("add", rich_help_panel="Register")
def ecosystems_add(
    slug: Annotated[
        Optional[str], typer.Option(help="Ecosystem slug (e.g. ethereum).")
    ] = None,
) -> None:
    """Scaffold a new [cyan]ecosystems/<slug>.yml[/cyan] with an initial IP source."""
    if not slug:
        slug = typer.prompt("Ecosystem slug (lowercase, no spaces)")
    slug = slug.strip().lower()

    target = ECOSYSTEMS_DIR / f"{slug}.yml"
    if target.exists():
        console.print(
            f"[red]{target} already exists. Use 'ecosystems add-source' to add a source.[/red]"
        )
        raise typer.Exit(1)

    display_name = typer.prompt("Display name", default=slug.capitalize())

    console.print("\n[bold]Initial IP source[/bold]")
    src_slug = typer.prompt("Source slug (e.g. eips)", default="proposals")
    src_display = typer.prompt(
        "Source display name", default=f"{display_name} Improvement Proposals"
    )
    acronym = typer.prompt("Proposal acronym (e.g. EIP)").upper()
    repo_owner = typer.prompt("GitHub repository owner")
    repo_name = typer.prompt("GitHub repository name")
    prefix = typer.prompt("Document file prefix (e.g. eip)", default=acronym.lower())

    config = {
        "slug": slug,
        "display_name": display_name,
        "sources": {
            src_slug: _build_source_scaffold(
                slug, src_slug, src_display, acronym, repo_owner, repo_name, prefix
            )
        },
    }

    target.write_text(
        yaml.dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    console.print(f"\n[green]Created {target}[/green]")
    console.print(
        f"Edit the file to complete the config, then run:\n"
        f"  python main.py ecosystems show {slug}"
    )


@eco_app.command("add-source", rich_help_panel="Register")
def ecosystems_add_source(
    slug: Annotated[str, typer.Argument(help="Ecosystem slug to add a source to.")],
) -> None:
    """Append a new IP catalog/source to an existing ecosystem YAML."""
    eco = _get_ecosystem(slug)
    target = ECOSYSTEMS_DIR / f"{slug}.yml"
    if not target.exists():
        console.print(f"[red]{target} not found.[/red]")
        raise typer.Exit(1)

    src_slug = typer.prompt("New source slug")
    if src_slug in eco.get("sources", {}):
        console.print(f"[red]Source '{src_slug}' already exists in '{slug}'.[/red]")
        raise typer.Exit(1)

    src_display = typer.prompt("Source display name")
    acronym = typer.prompt("Proposal acronym").upper()
    repo_owner = typer.prompt("GitHub repository owner")
    repo_name = typer.prompt("GitHub repository name")
    prefix = typer.prompt("Document file prefix", default=acronym.lower())

    raw = yaml.safe_load(target.read_text(encoding="utf-8"))
    raw.setdefault("sources", {})[src_slug] = _build_source_scaffold(
        slug, src_slug, src_display, acronym, repo_owner, repo_name, prefix
    )
    target.write_text(
        yaml.dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    console.print(f"\n[green]Added source '{src_slug}' to {target}[/green]")
    console.print(
        f"Edit the file to complete the config, then run:\n  python main.py run --ecosystem {slug} --source {src_slug}"
    )


def _build_source_scaffold(
    eco_slug: str,
    src_slug: str,
    display_name: str,
    acronym: str,
    repo_owner: str,
    repo_name: str,
    prefix: str,
) -> dict:
    return {
        "display_name": display_name,
        "proposal_acronym": acronym,
        "proposal_term_singular": f"{display_name[:-1] if display_name.endswith('s') else display_name}",
        "proposal_term_plural": display_name,
        "source_type": "github_repo",
        "repository_owner": repo_owner,
        "repository_name": repo_name,
        "harvest": f"ip_data/{eco_slug}/{src_slug}/01_harvest",
        "preprocess": f"ip_data/{eco_slug}/{src_slug}/02_preprocess",
        "analysis": f"ip_data/{eco_slug}/{src_slug}/03_analysis",
        "postprocess": f"ip_data/{eco_slug}/{src_slug}/04_postprocess",
        "document_prefix": prefix,
        "primary_id_field": prefix,
        "document_file_pattern": rf"^{prefix}-\d+\.(mediawiki|md|rst)$",
        "document_dir_pattern": rf"^{prefix}-\d+$",
        "reference_pattern": rf"\b{acronym}[-#\s]?(\d+)\b",
        "max_proposal_id": 9999,
        "stop_words_file": "assets/stopwords/en_basic.txt",
        "preamble": {
            "required_fields": [prefix, "title", "author", "status", "type", "created"],
            "optional_fields": ["discussions_to", "requires", "replaces"],
            "field_aliases": {},
            "expected_headlines": {"abstract": 2, "motivation": 2, "specification": 2},
            "list_valued_fields": ["author"],
        },
        "classification": {
            "dimensions": {
                "status": {"aliases": {}},
                "type": {"aliases": {}},
            },
            "regimes": [],
        },
    }


if __name__ == "__main__":
    app()
