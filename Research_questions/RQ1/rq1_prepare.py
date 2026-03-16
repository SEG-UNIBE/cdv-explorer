import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from analysis.authorship import extract_authorship_metrics
from Research_questions.common.artifact_io import load_network_data


def prepare_rq1_payload(network_data: Dict[str, Any]) -> Dict[str, Any]:
    nodes = network_data.get("nodes", [])
    authorship = extract_authorship_metrics(nodes)

    return {
        "meta": {
            "node_count": len(nodes),
            "author_count": authorship["author_count"],
            "generated_metrics": [
                "top_authors",
                "bips_per_year",
                "author_contribution_histogram",
                "top_10_share",
                "collaboration_network",
            ],
        },
        "top_authors": authorship["top_authors"],
        "bips_per_year": authorship["proposals_per_year"],
        "author_contribution_histogram": authorship["author_contribution_histogram"],
        "top_10_share": {
            "total_bips": authorship["top_10_share"]["total_proposals"],
            "bips_by_top_10_authors": authorship["top_10_share"]["proposals_by_top_10_authors"],
            "percentage": authorship["top_10_share"]["percentage"],
        },
        "collaboration_network": authorship["collaboration_network"],
    }


def save_payload(payload: Dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    print(f"Saved RQ1 artifact: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare RQ1 visualization data from network_data artifacts.")
    parser.add_argument("--stichtag", help="Snapshot label YYYY-MM-DD.")
    parser.add_argument(
        "--output-dir",
        default="Research_questions/artifacts/rq1",
        help="Directory for RQ1 prepared artifacts.",
    )
    args = parser.parse_args()

    data = load_network_data(stichtag=args.stichtag, prefer_json=True)
    payload = prepare_rq1_payload(data)

    snapshot_label = args.stichtag or "latest"
    script_dir = Path(__file__).resolve().parents[2]
    out_path = script_dir / args.output_dir / f"rq1_{snapshot_label}.json"
    save_payload(payload, out_path)


if __name__ == "__main__":
    main()
