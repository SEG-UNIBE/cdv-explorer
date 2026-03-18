import argparse
import json
from pathlib import Path
from typing import Any, Dict

from ecosystem_config import ACTIVE_ECOSYSTEM

from analysis.artifact_io import load_network_data
from analysis.classification import prepare_classification_payload


def save_payload(payload: Dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare classification artifact from network_data.")
    parser.add_argument("--snapshot", help="Snapshot label YYYY-MM-DD.")
    parser.add_argument(
        "--output-dir",
        default=f"{ACTIVE_ECOSYSTEM['analysis']}",
        help="Root analysis directory where <snapshot>/classification/classification_payload.json is written.",
    )
    args = parser.parse_args()

    data = load_network_data(snapshot=args.snapshot)
    payload = prepare_classification_payload(data)

    snapshot_label = args.snapshot or "latest"
    repo_root = Path(__file__).resolve().parents[2]
    out_path = repo_root / args.output_dir / snapshot_label / "classification" / "classification_payload.json"
    save_payload(payload, out_path)


if __name__ == "__main__":
    main()
