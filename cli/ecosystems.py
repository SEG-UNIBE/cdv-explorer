"""`ecosystems` sub-app: inspect and scaffold ecosystem YAML configs."""

from __future__ import annotations

import json
from typing import Annotated

import typer
import yaml
from rich.table import Table

from cli.common import ECOSYSTEMS_DIR, _get_ecosystem, console
from ecosystems import ECOSYSTEM_REGISTRY

eco_app = typer.Typer(
    help="List, inspect, and scaffold ecosystem configs ([cyan]ecosystems/*.yml[/cyan]).",
    rich_markup_mode="rich",
    add_completion=False,
    no_args_is_help=True,
)


@eco_app.command("list", rich_help_panel="Inspect")
def ecosystems_list() -> None:
    """List all registered ecosystems."""
    table = Table("Slug", "Display name", "Sources", title="Registered Ecosystems")
    for slug, eco in sorted(ECOSYSTEM_REGISTRY.items()):
        sources = eco.get("sources", {})
        src_summary = ", ".join(
            f"{source_slug} ({source.get('proposal_acronym', '?')})"
            for source_slug, source in sources.items()
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
        str | None, typer.Option(help="Ecosystem slug (e.g. ethereum).")
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

