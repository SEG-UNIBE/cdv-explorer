import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from Research_questions.common.artifact_io import load_network_data


STATUS_GROUP_MAP = {
    "Draft": "In Progress",
    "Review": "In Progress",
    "Proposed": "In Progress",
    "Obsolete": "Inactive",
    "Final": "Completed",
    "Active": "Completed",
    "Rejected": "Inactive",
    "Withdrawn": "Inactive",
    "Deferred": "Inactive",
    "Replaced": "Inactive",
}

TYPE_CLEAN_MAP = {
    "Standard": "Standards Track",
    "Standards": "Standards Track",
    "Standard Track": "Standards Track",
    "Standards-Track": "Standards Track",
}


def _clean_base(value: Any, fallback: str) -> str:
    text = str(value).strip() if value is not None else ""
    return text or fallback


def _base_status(status_text: str) -> str:
    return status_text.split("(")[0].strip()


def _extract_year(date_text: Any) -> int | None:
    if not date_text:
        return None
    try:
        return datetime.strptime(str(date_text), "%Y-%m-%d").year
    except ValueError:
        return None


def _node_triplet(node: Dict[str, Any]) -> Tuple[str, str, str]:
    layer = _clean_base(node.get("group"), "Unknown Layer")
    status = _clean_base(node.get("status"), "Unknown Status")
    kind = _clean_base(node.get("type"), "Unknown Type")
    return layer, status, kind


def build_sankey_links(nodes: List[Dict[str, Any]], grouped_status: bool) -> List[Dict[str, Any]]:
    links = Counter()

    for node in nodes:
        layer, status, kind = _node_triplet(node)

        if grouped_status:
            status = STATUS_GROUP_MAP.get(_base_status(status), _base_status(status))
            kind = TYPE_CLEAN_MAP.get(kind, kind)
            if "Unknown" in layer:
                layer = "Other"
            if "Unknown" in status:
                status = "Unknown Status"
            if "Unknown" in kind:
                kind = "Unknown Type"
        else:
            if "Unknown" in layer or "Unknown" in status or "Unknown" in kind:
                continue

        links[(layer, status)] += 1
        links[(status, kind)] += 1

    return [
        {"source": source, "target": target, "count": count}
        for (source, target), count in sorted(links.items(), key=lambda x: x[1], reverse=True)
    ]


def build_status_distribution_by_layer(nodes: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    grouped = defaultdict(Counter)
    for node in nodes:
        layer = _clean_base(node.get("group"), "Unknown")
        status = _clean_base(node.get("status"), "Unknown")
        grouped[layer][status] += 1

    out: Dict[str, Dict[str, int]] = {}
    for layer in sorted(grouped.keys()):
        out[layer] = dict(sorted(grouped[layer].items(), key=lambda x: x[0]))
    return out


def build_status_over_time(nodes: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    yearly = defaultdict(Counter)

    for node in nodes:
        year = _extract_year(node.get("created"))
        if year is None:
            continue
        status = _clean_base(node.get("status"), "Unknown")
        yearly[year][status] += 1

    out: Dict[str, Dict[str, int]] = {}
    for year in sorted(yearly.keys()):
        out[str(year)] = dict(sorted(yearly[year].items(), key=lambda x: x[0]))
    return out


def prepare_rq2_payload(network_data: Dict[str, Any]) -> Dict[str, Any]:
    nodes = network_data.get("nodes", [])

    return {
        "meta": {
            "node_count": len(nodes),
            "generated_metrics": [
                "sankey_full",
                "sankey_grouped",
                "status_distribution_by_layer",
                "status_over_time",
            ],
        },
        "sankey_full": {
            "links": build_sankey_links(nodes, grouped_status=False),
        },
        "sankey_grouped": {
            "links": build_sankey_links(nodes, grouped_status=True),
        },
        "status_distribution_by_layer": build_status_distribution_by_layer(nodes),
        "status_over_time": build_status_over_time(nodes),
    }


def save_payload(payload: Dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    print(f"Saved RQ2 artifact: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare RQ2 visualization data from network_data artifacts.")
    parser.add_argument("--stichtag", help="Snapshot label YYYY-MM-DD.")
    parser.add_argument(
        "--output-dir",
        default="Research_questions/artifacts/rq2",
        help="Directory for RQ2 prepared artifacts.",
    )
    args = parser.parse_args()

    data = load_network_data(stichtag=args.stichtag, prefer_json=True)
    payload = prepare_rq2_payload(data)

    snapshot_label = args.stichtag or "latest"
    script_dir = Path(__file__).resolve().parents[2]
    out_path = script_dir / args.output_dir / f"rq2_{snapshot_label}.json"
    save_payload(payload, out_path)


if __name__ == "__main__":
    main()
