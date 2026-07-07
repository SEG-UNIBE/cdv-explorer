"""Shared console, config lookup, and snapshot helpers for the CLI modules."""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

import typer
from rich.console import Console
from tqdm import tqdm

from ecosystems import ECOSYSTEM_REGISTRY

ECOSYSTEMS_DIR = Path(__file__).resolve().parents[1] / "ecosystems"
console = Console()


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


def _validate_snapshot_date(snapshot: str) -> None:
    try:
        date.fromisoformat(snapshot)
    except ValueError:
        console.print(f"[red]Invalid snapshot date '{snapshot}'. Use YYYY-MM-DD.[/red]")
        raise typer.Exit(1)
