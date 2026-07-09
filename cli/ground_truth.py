"""`ground-truth` sub-app: manage curated ground-truth benchmark files."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from cli.common import (
    _get_ecosystem,
    _get_source,
    _snapshot_labels,
    _validate_snapshot_date,
    console,
)
from ecosystems import ECOSYSTEM_REGISTRY

ground_truth_app = typer.Typer(
    help="Manage human-curated ground-truth benchmark files.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)


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


def _payload_snapshot_labels_with_networks(postprocess_root: Path) -> list[str]:
    labels: list[str] = []
    for snapshot in _snapshot_labels(postprocess_root):
        network_path = (
            postprocess_root / snapshot / "dependencies" / "network_data.json"
        )
        if network_path.exists():
            labels.append(snapshot)
    return labels


@ground_truth_app.command("sample-ips", rich_help_panel="Manage")
def ground_truth_sample_ips(
    ecosystem: Annotated[
        str | None, typer.Option("--ecosystem", "-e", help="Ecosystem slug.")
    ] = None,
    source: Annotated[
        str | None, typer.Option("--source", help="Source slug to sample from.")
    ] = None,
    snapshot: Annotated[
        str | None,
        typer.Option("--snapshot", "-s", help="Snapshot date (YYYY-MM-DD)."),
    ] = None,
    count: Annotated[
        int | None,
        typer.Option("--count", help="Number of new reviewed IP rows to prefill."),
    ] = None,
    seed: Annotated[
        int | None,
        typer.Option(
            "--seed", help="Random seed for reproducible stratified sampling."
        ),
    ] = None,
    era_buckets: Annotated[
        int | None,
        typer.Option(
            "--era-buckets", min=1, help="Number of time-based strata to use."
        ),
    ] = None,
    density_basis: Annotated[
        str | None,
        typer.Option(
            "--density-basis",
            help="Density basis: all_methods, regex_only, llm_only, or preamble_only.",
        ),
    ] = None,
    density_low_max: Annotated[
        int | None,
        typer.Option(
            "--density-low-max",
            min=0,
            help="Upper bound for the `low` extracted-density bucket; values above this become `high`.",
        ),
    ] = None,
    proposal_type: Annotated[
        str | None,
        typer.Option(
            "--proposal-type",
            help="Optional exact proposal type filter (e.g. Specification).",
        ),
    ] = None,
    reviewer: Annotated[
        str | None,
        typer.Option(
            "--reviewer", help="Optional reviewer name to prefill in new rows."
        ),
    ] = None,
    replace: Annotated[
        bool | None,
        typer.Option(
            "--replace/--append", help="Overwrite ips_append.xlsx or append new rows."
        ),
    ] = None,
    wizard: Annotated[
        bool, typer.Option("--wizard", help="Force interactive step-by-step prompts.")
    ] = False,
) -> None:
    """Prefill ground_truth/ips_append.xlsx from a stratified source-IP sample."""
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

    available_snapshots = _payload_snapshot_labels_with_networks(
        Path(str(src["postprocess"]))
    )
    if not available_snapshots:
        console.print(
            f"[red]No postprocess snapshots with dependency network payloads found for {ecosystem}/{source}.[/red]"
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
        Path(str(src["postprocess"])) / snapshot / "dependencies" / "network_data.json"
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
