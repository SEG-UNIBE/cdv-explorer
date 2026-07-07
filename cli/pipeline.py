"""Root `run` command and full source-pipeline orchestration."""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Annotated, Optional

import typer

from cli.artifacts import _rebuild_combined_source_artifacts, _rebuild_source_artifacts
from cli.common import (
    _get_ecosystem,
    _get_source,
    _run_stage,
    _validate_snapshot_date,
    console,
)
from cli.llm_runs import _existing_llm_model_run_counts, _failed_llm_model_focus
from ecosystems import ECOSYSTEM_REGISTRY
from pipeline.source_context import SourceContext


def _build_file_manifest(harvest_root: Path, src: dict) -> dict:
    prefix = src["document_prefix"]
    file_pattern = re.compile(src["document_file_pattern"], re.IGNORECASE)
    files: dict[str, str] = {}
    for path in harvest_root.iterdir():
        if not file_pattern.match(path.name):
            continue
        stem = path.stem
        id_part = (
            stem[len(prefix) + 1 :]
            if stem.lower().startswith(f"{prefix}-")
            else stem
        )
        try:
            id_key = str(int(id_part))
        except ValueError:
            id_key = id_part.upper()
        files[id_key] = path.name
    return files


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
    from pipeline.preprocess import get_enricher, get_extractor

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
            path for path in harvest_root.iterdir() if file_pattern.match(path.name)
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
    if (
        not skipllm
        and source_context.llm_model
        and output_dir.exists()
        and not rerun_failed_only
    ):
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

