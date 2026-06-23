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
        id_part = stem[len(prefix) + 1:] if stem.lower().startswith(f"{prefix}-") else stem
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


def _latest_snapshot_labels(analysis_root: Path) -> list[str]:
    if not analysis_root.is_dir():
        return []
    return sorted(
        (p.name for p in analysis_root.iterdir() if p.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", p.name)),
        reverse=True,
    )


def _snapshot_labels(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    return sorted(
        (p.name for p in root.iterdir() if p.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", p.name)),
    )


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
    selected_sources = {source_slug: _get_source(eco, source_slug)} if source_slug else sources
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


def _rebuild_source_artifacts(eco_slug: str, src_slug: str, src: dict, snapshot: str, *, stage_label: str = "Build analysis and postprocess artifacts") -> None:
    """Rebuild analysis/postprocess artifacts for one source from existing preprocess JSON."""
    from analysis.pipeline import prepare_ecosystem_artifacts
    from analysis.validation import validate_ground_truth_curated_file, validate_source_snapshot

    harvest_root = Path(src["harvest"])
    preprocess_dir = Path(src["preprocess"]) / snapshot
    analysis_root = Path(src["analysis"])
    postprocess_root = Path(src["postprocess"])
    source_context = SourceContext.from_config(src, ecosystem_slug=eco_slug, source_slug=src_slug)

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

    ground_truth_validation = validate_ground_truth_curated_file(eco_slug, _get_ecosystem(eco_slug))
    if not ground_truth_validation.ok:
        console.print(f"[red]Ground-truth validation failed for {eco_slug}:[/red]")
        for error in ground_truth_validation.errors[:20]:
            console.print(f"  [red]-[/red] {error}")
        if len(ground_truth_validation.errors) > 20:
            console.print(f"  [red]-[/red] ... and {len(ground_truth_validation.errors) - 20} more")
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
        console.print(f"[red]Snapshot validation failed for {eco_slug}/{src_slug}/{snapshot}:[/red]")
        for error in validation.errors[:20]:
            console.print(f"  [red]-[/red] {error}")
        if len(validation.errors) > 20:
            console.print(f"  [red]-[/red] ... and {len(validation.errors) - 20} more")
        raise typer.Exit(1)


def _count_source_combinations(source_count: int) -> int:
    if source_count < 2:
        return 0
    return (2 ** source_count) - source_count - 1


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
        validation = validate_combined_snapshot(ecosystem_slug=eco_slug, combo_key=combo_key, snapshot=snapshot)
        if not validation.ok:
            console.print(f"[red]Snapshot validation failed for {eco_slug}/{combo_key}/{snapshot}:[/red]")
            for error in validation.errors[:20]:
                console.print(f"  [red]-[/red] {error}")
            if len(validation.errors) > 20:
                console.print(f"  [red]-[/red] ... and {len(validation.errors) - 20} more")
            raise typer.Exit(1)


def _rebuild_artifacts_for_targets(eco_slug: str, eco: dict, targets: dict[str, dict], snapshot: str) -> None:
    if len(targets) == 1:
        src_slug, src_cfg = next(iter(targets.items()))
        _rebuild_source_artifacts(eco_slug, src_slug, src_cfg, snapshot)
        return

    for src_slug, src_cfg in targets.items():
        console.rule(f"[bold]{eco_slug} / {src_slug}[/bold]")
        _rebuild_source_artifacts(eco_slug, src_slug, src_cfg, snapshot)
    _rebuild_combined_source_artifacts(eco_slug, eco, snapshot)


def _analysis_dirs_for_ecosystem(eco_dir: Path, eco_config: dict | None = None) -> list[tuple[str | None, Path]]:
    direct = eco_dir / "03_analysis"
    if direct.is_dir():
        matched_source = None
        for source_slug, source in sorted((eco_config or {}).get("sources", {}).items()):
            if Path(source.get("analysis", "")) == direct:
                matched_source = source_slug
                break
        return [(matched_source, direct)]

    source_dirs = [
        (source_dir.name, source_dir / "03_analysis")
        for source_dir in sorted(eco_dir.iterdir())
        if source_dir.is_dir() and source_dir.name != "_combined" and (source_dir / "03_analysis").is_dir()
    ]
    combined_root = eco_dir / "_combined"
    combo_dirs = [
        (combo_dir.name, combo_dir / "03_analysis")
        for combo_dir in sorted(combined_root.iterdir())
        if combined_root.is_dir() and combo_dir.is_dir() and (combo_dir / "03_analysis").is_dir()
    ] if combined_root.is_dir() else []
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
                pass
        ids.add(part)
        ids.add(part.upper())
    return ids or None


def _run_source_pipeline(eco_slug: str, src_slug: str, src: dict, snapshot: str, skipllm: bool, focus: set[str] | None = None) -> None:
    """Run the full pipeline for one source."""
    from pipeline.harvest import get_harvester
    from pipeline.preprocess import get_extractor, get_enricher

    harvest_root = Path(src["harvest"])
    preprocess_root = Path(src["preprocess"])
    analysis_root = Path(src["analysis"])
    output_dir = preprocess_root / snapshot
    prefix = src["document_prefix"]
    source_context = SourceContext.from_config(src, ecosystem_slug=eco_slug, source_slug=src_slug)

    harvester = get_harvester(src.get("harvester", "github_repo"))
    extractor = get_extractor(src.get("preprocessor", "rfc_preamble"))
    enricher = get_enricher()

    _run_stage("Step 1/4 · I. Harvest".ljust(28), 3, "step",
               lambda u: harvester(src_config=src, snapshot=snapshot, local_dir=harvest_root, progress_callback=u))

    commit = subprocess.run(
        ["git", "-C", str(harvest_root), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    manifest = {
        "commit": commit,
        "files": _build_file_manifest(harvest_root, src),
    }
    manifest_path = analysis_root / snapshot / f"{prefix}_files.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    preprocess_exists = output_dir.exists() and any(output_dir.glob("*.json"))
    if focus is not None and preprocess_exists:
        console.print(f"  [green]✓[/green]  {'Step 2/4 · II. Preprocess'.ljust(28)}  [dim]skipped — focus run, existing preambles preserved[/dim]")
    else:
        file_pattern = re.compile(src["document_file_pattern"], re.IGNORECASE)
        proposal_files = [p for p in harvest_root.iterdir() if file_pattern.match(p.name)]
        _run_stage("Step 2/4 · II. Preprocess".ljust(28), len(proposal_files), "ip",
                   lambda u: extractor(src_config=src, harvest_dir=harvest_root, output_dir=output_dir, progress_callback=u))

    json_files = list(output_dir.glob("*.json")) if output_dir.exists() else []
    focus_note = f"  (focus: {len(focus)}/{len(json_files)} ip)" if focus else ""
    _run_stage(f"{'Step 3/4 · III. Analysis'.ljust(28)}{focus_note}", len(json_files), "ip",
               lambda u: enricher(
                   src_config=src,
                   preprocess_dir=output_dir,
                   harvest_dir=harvest_root,
                   skip_llm=skipllm,
                   focus=focus,
                   source_context=source_context,
                   progress_callback=u))

    _rebuild_source_artifacts(eco_slug, src_slug, src, snapshot, stage_label="Step 4/4 · IV. Postprocess".ljust(28))


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

@app.command(rich_help_panel="Discovery")
def doctor() -> None:
    """Check local tools, dependencies, configs, and snapshot artifacts without changing files."""
    table = Table("Status", "Check", "Details", title="CDV-Explorer Doctor")
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
        f"Missing: {', '.join(missing_packages)}" if missing_packages else f"{installed_count} packages installed",
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
        "react/node_modules present" if react_node_modules.is_dir() else "Run `cd react && npm install` before frontend work",
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
        ) if ecosystems_missing_llm_model else "llm.model configured for ecosystems with sources",
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
        f"Not cloned yet: {', '.join(harvest_warnings)}" if harvest_warnings else "all configured harvest repos are git clones",
    )
    ok &= _doctor_row(
        table,
        "OK" if any(": none" not in detail for detail in snapshot_details) else "WARN",
        "Snapshots",
        "; ".join(snapshot_details) if snapshot_details else "no configured sources",
    )

    validate_script = Path("scripts/validate_snapshots.py")
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
            "validation passed" if result.returncode == 0 else "validation failed; run `python3 scripts/validate_snapshots.py`",
        )
    else:
        ok &= _doctor_row(table, "WARN", "Snapshot artifacts", "scripts/validate_snapshots.py not found")

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
        f"Missing: {', '.join(missing_generated)}; run `cd react && npm run prebuild`" if missing_generated else "generated indexes present",
    )

    api_key_present = bool(os.getenv("OPENAI_API_KEY")) or Path("apikey.secret").exists()
    ok &= _doctor_row(
        table,
        "OK" if api_key_present else "WARN",
        "OpenAI key",
        "available for LLM extraction" if api_key_present else "not set; `run --skipllm` still works",
    )

    console.print(table)
    if ok:
        console.print("[green]Doctor completed: no blocking issues found.[/green]")
        return

    console.print("[red]Doctor found blocking issues.[/red]")
    raise typer.Exit(1)


@app.command(rich_help_panel="Pipeline")
def run(
    ecosystem: Annotated[Optional[str], typer.Option("--ecosystem", "-e", help="Ecosystem slug (default: first registered).")] = None,
    source: Annotated[Optional[str], typer.Option("--source", help="Source slug (default: all sources).")] = None,
    snapshot: Annotated[str, typer.Option("--snapshot", "-s", help="Snapshot date (YYYY-MM-DD). Required.")] = ...,
    skipllm: Annotated[bool, typer.Option("--skipllm", help="Skip LLM-based extraction.")] = False,
    focus: Annotated[Optional[str], typer.Option("--focus", help="Comma-separated list of proposal IDs to process (e.g. '1-9,30-44,85,A0'). All others are skipped.")] = None,
) -> None:
    """Run the full pipeline for a snapshot. Runs all sources unless --source is given."""
    eco_slug = ecosystem or next(iter(ECOSYSTEM_REGISTRY), None)
    if not eco_slug:
        console.print("[red]No ecosystems registered. Add a .yml file to the ecosystems/ directory.[/red]")
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
        _run_source_pipeline(eco_slug, src_slug, src_cfg, snapshot, skipllm, focus_ids)
        elapsed = time.monotonic() - run_started
        console.print(f"\n[green]Done in {elapsed:.1f}s[/green]")
    else:
        run_started = time.monotonic()
        for src_slug, src_cfg in targets.items():
            console.rule(f"[bold]{eco_slug} / {src_slug}[/bold]")
            _run_source_pipeline(eco_slug, src_slug, src_cfg, snapshot, skipllm, focus_ids)
        _rebuild_combined_source_artifacts(eco_slug, eco, snapshot)
        elapsed = time.monotonic() - run_started
        console.print(f"\n[green]All sources done in {elapsed:.1f}s[/green]")


# ---------------------------------------------------------------------------
# artifacts
# ---------------------------------------------------------------------------

@artifacts_app.command("rebuild", rich_help_panel="Manage")
def artifacts_rebuild(
    ecosystem: Annotated[Optional[str], typer.Option("--ecosystem", "-e", help="Ecosystem slug (default: first registered).")] = None,
    source: Annotated[Optional[str], typer.Option("--source", help="Source slug (default: all sources).")] = None,
    snapshot: Annotated[Optional[str], typer.Option("--snapshot", "-s", help="Snapshot date (YYYY-MM-DD). Required unless --all is used.")] = None,
    all_snapshots: Annotated[bool, typer.Option("--all", help="Rebuild every existing preprocessed snapshot for the selected ecosystem/source.")] = False,
) -> None:
    """Rebuild analysis and postprocess artifacts from existing preprocessed JSON."""
    eco_slug = ecosystem or next(iter(ECOSYSTEM_REGISTRY), None)
    if not eco_slug:
        console.print("[red]No ecosystems registered. Add a .yml file to the ecosystems/ directory.[/red]")
        raise typer.Exit(1)
    eco = _get_ecosystem(eco_slug)
    if all_snapshots and snapshot:
        console.print("[red]Use either --all or --snapshot, not both.[/red]")
        raise typer.Exit(1)
    if not all_snapshots and not snapshot:
        console.print("[red]Missing option '--snapshot' / '-s'. Use --all to rebuild every preprocessed snapshot.[/red]")
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
            console.print(f"[yellow]No preprocessed snapshots found for {scope}.[/yellow]")
            raise typer.Exit(0)

        for snapshot_label in snapshots:
            console.rule(f"[bold]{eco_slug} / {snapshot_label}[/bold]")
            _rebuild_artifacts_for_targets(eco_slug, eco, targets, snapshot_label)
        elapsed = time.monotonic() - rebuild_started
        console.print(f"\n[green]Artifacts rebuilt for {len(snapshots)} snapshot(s) in {elapsed:.1f}s[/green]")
        return

    _rebuild_artifacts_for_targets(eco_slug, eco, targets, snapshot)
    elapsed = time.monotonic() - rebuild_started
    if len(targets) == 1:
        console.print(f"\n[green]Artifacts rebuilt in {elapsed:.1f}s[/green]")
    else:
        console.print(f"\n[green]Artifacts rebuilt for all sources in {elapsed:.1f}s[/green]")


# ---------------------------------------------------------------------------
# snapshots
# ---------------------------------------------------------------------------

def _print_snapshots(
    ecosystem: Annotated[Optional[str], typer.Option("--ecosystem", "-e", help="Filter by ecosystem.")] = None,
) -> None:
    ip_root = Path("ip_data")
    if not ip_root.exists():
        console.print("[yellow]No ip_data directory found.[/yellow]")
        raise typer.Exit(0)

    table = Table("Ecosystem", "Source", "Snapshot", "Path", title="Available Snapshots")
    found = False

    for eco_dir in sorted(ip_root.iterdir()):
        if not eco_dir.is_dir():
            continue
        slug = eco_dir.name
        if ecosystem and slug != ecosystem:
            continue
        for source_slug, analysis_dir in _analysis_dirs_for_ecosystem(eco_dir, ECOSYSTEM_REGISTRY.get(slug)):
            for snap_dir in sorted(analysis_dir.iterdir(), reverse=True):
                if snap_dir.is_dir():
                    table.add_row(slug, source_slug or "—", snap_dir.name, str(snap_dir))
                    found = True

    if found:
        console.print(table)
    else:
        suffix = f" for ecosystem '{ecosystem}'" if ecosystem else ""
        console.print(f"[yellow]No snapshots found{suffix}.[/yellow]")


@snapshots_app.callback(invoke_without_command=True)
def snapshots(
    ctx: typer.Context,
    ecosystem: Annotated[Optional[str], typer.Option("--ecosystem", "-e", help="Filter by ecosystem.")] = None,
) -> None:
    """List available snapshots found under ip_data/."""
    if ctx.invoked_subcommand is not None:
        return
    _print_snapshots(ecosystem=ecosystem)


@snapshots_app.command("list", rich_help_panel="Inspect")
def snapshots_list(
    ecosystem: Annotated[Optional[str], typer.Option("--ecosystem", "-e", help="Filter by ecosystem.")] = None,
) -> None:
    """List available snapshots found under ip_data/."""
    _print_snapshots(ecosystem=ecosystem)


@snapshots_app.command("remove", rich_help_panel="Manage")
def snapshots_remove(
    snapshot: Annotated[str, typer.Argument(help="Snapshot date to remove (YYYY-MM-DD).")],
    ecosystem: Annotated[str, typer.Option("--ecosystem", "-e", help="Ecosystem slug.")],
    source: Annotated[Optional[str], typer.Option("--source", help="Source slug. Omit to remove all sources in the ecosystem.")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show matching snapshot directories without deleting.")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Delete without an interactive confirmation prompt.")] = False,
) -> None:
    """Remove generated preprocess, analysis, and postprocess directories for a snapshot."""
    _validate_snapshot_date(snapshot)

    eco = _get_ecosystem(ecosystem)
    targets = _collect_snapshot_removal_targets(ecosystem, eco, source, snapshot)
    if not targets:
        scope = f"{ecosystem}/{source}" if source else ecosystem
        console.print(f"[yellow]No generated snapshot directories found for {scope} at {snapshot}.[/yellow]")
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
    console.print(f"[green]Removed {len(targets)} generated snapshot director{'y' if len(targets) == 1 else 'ies'}.[/green]")


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
            f"{s} ({v.get('proposal_acronym', '?')})"
            for s, v in sources.items()
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
    slug: Annotated[Optional[str], typer.Option(help="Ecosystem slug (e.g. ethereum).")] = None,
) -> None:
    """Scaffold a new [cyan]ecosystems/<slug>.yml[/cyan] with an initial IP source."""
    if not slug:
        slug = typer.prompt("Ecosystem slug (lowercase, no spaces)")
    slug = slug.strip().lower()

    target = ECOSYSTEMS_DIR / f"{slug}.yml"
    if target.exists():
        console.print(f"[red]{target} already exists. Use 'ecosystems add-source' to add a source.[/red]")
        raise typer.Exit(1)

    display_name = typer.prompt("Display name", default=slug.capitalize())

    console.print("\n[bold]Initial IP source[/bold]")
    src_slug = typer.prompt("Source slug (e.g. eips)", default="proposals")
    src_display = typer.prompt("Source display name", default=f"{display_name} Improvement Proposals")
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

    target.write_text(yaml.dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
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
    target.write_text(yaml.dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    console.print(f"\n[green]Added source '{src_slug}' to {target}[/green]")
    console.print(f"Edit the file to complete the config, then run:\n  python main.py run --ecosystem {slug} --source {src_slug}")


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
