import argparse
from pathlib import Path

from analysis.dependencies import (
    build_network_data,
    load_proposal_json_documents,
    save_network_data_artifacts,
)
from pipeline.source_context import SourceContext


def resolve_input_dir(
    repo_root: Path, snapshot: str | None, source_context: SourceContext
) -> Path:
    base_dir = repo_root / source_context.config["preprocess"]
    if snapshot:
        dated_dir = base_dir / snapshot
        if dated_dir.exists():
            return dated_dir
        raise FileNotFoundError(f"Snapshot directory not found: {dated_dir}")
    return base_dir


def main() -> None:
    source_context = SourceContext.default()
    parser = argparse.ArgumentParser(
        description="Build snapshot network_data artifacts from preprocessed proposal JSON files."
    )
    parser.add_argument(
        "--snapshot",
        help="Snapshot date (YYYY-MM-DD). If provided, reads from <preprocess>/<snapshot>/",
    )
    parser.add_argument(
        "--output-dir",
        default=f"{source_context.config['analysis']}",
        help="Root analysis directory where <snapshot>/dependencies/network_data.* will be written.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]

    input_dir = resolve_input_dir(repo_root, args.snapshot, source_context)
    proposal_data = load_proposal_json_documents(
        input_dir, source_context=source_context
    )
    network_data = build_network_data(
        proposal_data,
        id_field=source_context.primary_id_field,
        proposal_label=source_context.proposal_label,
        source_context=source_context,
    )

    snapshot_label = args.snapshot or "latest"
    output_stem = (
        repo_root / args.output_dir / snapshot_label / "dependencies" / "network_data"
    )
    save_network_data_artifacts(network_data, output_stem)


if __name__ == "__main__":
    main()
