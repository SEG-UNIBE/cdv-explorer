import argparse
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from ecosystem_config import ACTIVE_ECOSYSTEM

from analysis.dependencies.network import (
    build_network_data,
    load_proposal_json_documents,
    save_network_data_artifacts,
)


def resolve_input_dir(repo_root: Path, stichtag: str | None) -> Path:
    base_dir = repo_root / ACTIVE_ECOSYSTEM["json_directory"]
    if stichtag:
        dated_dir = base_dir / stichtag
        if dated_dir.exists():
            return dated_dir
        raise FileNotFoundError(f"STICHTAG directory not found: {dated_dir}")
    return base_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build snapshot network_data artifacts from preprocessed proposal JSON files."
    )
    parser.add_argument(
        "--stichtag",
        help="Snapshot date (YYYY-MM-DD). If provided, reads from <json_directory>/<stichtag>/",
    )
    parser.add_argument(
        "--output-dir",
        default=f"{ACTIVE_ECOSYSTEM['artifact_directory']}/dependencies",
        help="Directory where network_data artifacts are written.",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent

    input_dir = resolve_input_dir(repo_root, args.stichtag)
    proposal_data = load_proposal_json_documents(input_dir)
    network_data = build_network_data(
        proposal_data,
        id_field=ACTIVE_ECOSYSTEM["primary_id_field"],
        proposal_label=ACTIVE_ECOSYSTEM["proposal_acronym"],
    )

    snapshot_label = args.stichtag or "latest"
    output_stem = repo_root / args.output_dir / f"network_data_{snapshot_label}"
    save_network_data_artifacts(network_data, output_stem)


if __name__ == "__main__":
    main()
