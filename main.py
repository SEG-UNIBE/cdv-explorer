"""CDV Explorer command-line entrypoint."""

from __future__ import annotations

import typer

from cli.artifacts import artifacts_app
from cli.doctor import doctor
from cli.ecosystems import eco_app
from cli.ground_truth import ground_truth_app
from cli.pipeline import run
from cli.snapshots import snapshots_app

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

app.command(rich_help_panel="Discovery")(doctor)
app.command(rich_help_panel="Pipeline")(run)
app.add_typer(eco_app, name="ecosystems", rich_help_panel="Discovery")
app.add_typer(snapshots_app, name="snapshots", rich_help_panel="Discovery")
app.add_typer(artifacts_app, name="artifacts", rich_help_panel="Pipeline")
app.add_typer(ground_truth_app, name="ground-truth", rich_help_panel="Pipeline")


if __name__ == "__main__":
    app()
