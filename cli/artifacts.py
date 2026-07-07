"""`artifacts` sub-app: rebuild analysis/postprocess artifacts from preprocessed JSON."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated, Optional

import typer

from cli.common import (
    _get_ecosystem,
    _get_source,
    _run_stage,
    _snapshot_labels,
    _validate_snapshot_date,
    console,
)
from cli.llm_runs import _available_llm_models_in_preprocess_dir
from ecosystems import ECOSYSTEM_REGISTRY
from pipeline.source_context import SourceContext

artifacts_app = typer.Typer(
    help="Rebuild generated analysis and postprocess artifacts from preprocessed JSON.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)


def _common_preprocess_snapshot_labels(sources: dict[str, dict]) -> list[str]:
    snapshot_sets = [
        set(_snapshot_labels(Path(src.get("preprocess", ""))))
        for src in sources.values()
    ]
    if not snapshot_sets:
        return []
    return sorted(set.intersection(*snapshot_sets))


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
