import argparse
from pathlib import Path

from pipeline.ecosystem_config import ACTIVE_ECOSYSTEM

from analysis.dependencies import (
    build_network_data,
    load_proposal_json_documents,
    save_network_data_artifacts,
)


def resolve_input_dir(repo_root: Path, snapshot: str | None) -> Path:
    base_dir = repo_root / ACTIVE_ECOSYSTEM["preprocess"]
    if snapshot:
        dated_dir = base_dir / snapshot
        if dated_dir.exists():
            return dated_dir
        raise FileNotFoundError(f"Snapshot directory not found: {dated_dir}")
    return base_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build snapshot network_data artifacts from preprocessed proposal JSON files."
    )
    parser.add_argument(
        "--snapshot",
        help="Snapshot date (YYYY-MM-DD). If provided, reads from <preprocess>/<snapshot>/",
    )
    parser.add_argument(
        "--output-dir",
        default=f"{ACTIVE_ECOSYSTEM['analysis']}",
        help="Root analysis directory where <snapshot>/dependencies/network_data.* will be written.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]

    input_dir = resolve_input_dir(repo_root, args.snapshot)
    proposal_data = load_proposal_json_documents(input_dir)
    network_data = build_network_data(
        proposal_data,
        id_field=ACTIVE_ECOSYSTEM["primary_id_field"],
        proposal_label=ACTIVE_ECOSYSTEM["proposal_acronym"],
    )

    snapshot_label = args.snapshot or "latest"
    output_stem = repo_root / args.output_dir / snapshot_label / "dependencies" / "network_data"
    save_network_data_artifacts(network_data, output_stem)


if __name__ == "__main__":
    main()
