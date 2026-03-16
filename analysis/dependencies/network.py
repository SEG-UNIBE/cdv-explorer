import json
import csv
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List


def normalize_proposal_ids(field: Any, proposal_label: str = "IP") -> List[str]:
    if not field:
        return []

    if isinstance(field, list):
        raw_items = field
    else:
        raw_items = str(field).split(",")

    result = []
    label = re.escape(proposal_label)
    id_pattern = re.compile(rf"^\s*(?:{label}[-\s]*)?\d+\s*$", re.IGNORECASE)

    for item in raw_items:
        text = str(item)
        if id_pattern.match(text):
            normalized = re.sub(rf"(?i)^\s*{label}[-\s]*", "", text).strip()
            result.append(normalized)
    return result


def load_proposal_json_documents(source_dir: Path) -> List[Dict[str, Any]]:
    documents: List[Dict[str, Any]] = []
    for file_path in sorted(source_dir.glob("*.json")):
        try:
            with file_path.open("r", encoding="utf-8") as handle:
                documents.append(json.load(handle))
        except json.JSONDecodeError:
            print(f"Warning: failed to parse {file_path.name}")
    return documents


def build_network_data(
    proposal_data: Iterable[Dict[str, Any]],
    id_field: str = "id",
    proposal_label: str = "IP",
) -> Dict[str, Any]:
    nodes = []
    reference_links = []
    dependency_links = []
    requires_links = []
    replaces_links = []
    superseded_by_links = []
    node_ids = set()

    for proposal in proposal_data:
        if not proposal:
            continue

        preamble = proposal.get("raw", {}).get("preamble", {})
        insights = proposal.get("insights", {})
        proposal_id = preamble.get(id_field)

        if not proposal_id:
            continue

        proposal_id = str(proposal_id)
        if proposal_id not in node_ids:
            nodes.append(
                {
                    "id": proposal_id,
                    "group": preamble.get("layer"),
                    "compliance_score": preamble.get("compliance_score"),
                    "created": preamble.get("created"),
                    "author": preamble.get("author"),
                    "word_list": insights.get("word_list"),
                    "status": preamble.get("status"),
                    "type": preamble.get("type"),
                }
            )
            node_ids.add(proposal_id)

    for proposal in proposal_data:
        if not proposal:
            continue

        preamble = proposal.get("raw", {}).get("preamble", {})
        insights = proposal.get("insights", {})
        proposal_id = preamble.get(id_field)

        if not proposal_id:
            continue

        proposal_id = str(proposal_id)
        if proposal_id not in node_ids:
            continue

        references_field = insights.get(
            "references",
            insights.get("proposal_references", insights.get("bip_references")),
        )

        for ref_id in normalize_proposal_ids(references_field, proposal_label=proposal_label):
            if ref_id in node_ids:
                reference_links.append({"source": proposal_id, "target": ref_id, "value": 1})

        for dep_id in normalize_proposal_ids(insights.get("dependencies"), proposal_label=proposal_label):
            if dep_id in node_ids:
                dependency_links.append({"source": proposal_id, "target": dep_id, "value": 1})

        for req_id in normalize_proposal_ids(preamble.get("requires"), proposal_label=proposal_label):
            if req_id in node_ids:
                requires_links.append({"source": proposal_id, "target": req_id, "value": 1})

        for rep_id in normalize_proposal_ids(preamble.get("replaces"), proposal_label=proposal_label):
            if rep_id in node_ids:
                replaces_links.append({"source": proposal_id, "target": rep_id, "value": 1})

        for sup_id in normalize_proposal_ids(preamble.get("superseded_by"), proposal_label=proposal_label):
            if sup_id in node_ids:
                superseded_by_links.append({"source": proposal_id, "target": sup_id, "value": 1})

    return {
        "nodes": nodes,
        "links": {
            "references": reference_links,
            "dependencies": dependency_links,
            "requires": requires_links,
            "replaces": replaces_links,
            "superseded_by": superseded_by_links,
        },
    }


def save_network_data_artifacts(network_data: Dict[str, Any], output_stem: Path) -> None:
    output_stem.parent.mkdir(parents=True, exist_ok=True)

    json_path = output_stem.with_suffix(".json")

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(network_data, handle, ensure_ascii=False, indent=2)

    nodes_csv_path = output_stem.parent / f"{output_stem.name}_nodes.csv"
    with nodes_csv_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = ["id", "group", "compliance_score", "created", "author", "status", "type"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for node in network_data.get("nodes", []):
            row = {k: node.get(k) for k in fieldnames}
            if isinstance(row.get("author"), list):
                row["author"] = " | ".join(str(a) for a in row["author"])
            writer.writerow(row)

    for link_type, links in network_data.get("links", {}).items():
        links_csv_path = output_stem.parent / f"{output_stem.name}_{link_type}_edges.csv"
        with links_csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["source", "target", "value"])
            writer.writeheader()
            for link in links:
                writer.writerow(
                    {
                        "source": link.get("source"),
                        "target": link.get("target"),
                        "value": link.get("value", 1),
                    }
                )

    print(f"Saved JSON artifact: {json_path}")
    print(f"Saved CSV artifact: {nodes_csv_path}")
