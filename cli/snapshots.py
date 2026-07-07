"""`snapshots` sub-app: inspect and remove generated snapshot directories."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from cli.common import (
    _get_ecosystem,
    _get_source,
    _validate_snapshot_date,
    console,
)
from ecosystems import ECOSYSTEM_REGISTRY

snapshots_app = typer.Typer(
    help="List and remove generated snapshot artifacts.",
    rich_markup_mode="rich",
    invoke_without_command=True,
)


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


def _print_snapshots(
    ecosystem: Annotated[
        str | None, typer.Option("--ecosystem", "-e", help="Filter by ecosystem.")
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
        str | None, typer.Option("--ecosystem", "-e", help="Filter by ecosystem.")
    ] = None,
) -> None:
    """List available snapshots found under ip_data/."""
    if ctx.invoked_subcommand is not None:
        return
    _print_snapshots(ecosystem=ecosystem)


@snapshots_app.command("list", rich_help_panel="Inspect")
def snapshots_list(
    ecosystem: Annotated[
        str | None, typer.Option("--ecosystem", "-e", help="Filter by ecosystem.")
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
        str | None,
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

