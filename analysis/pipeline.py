import json
import csv
from pathlib import Path
from typing import Any, Dict, List

from analysis.authorship import extract_authorship_metrics
from analysis.authorship import prepare_authorship_payload
from analysis.classification import prepare_classification_payload
from analysis.conformity import extract_conformity_metrics
from analysis.dependencies import (
    build_network_data,
    load_proposal_json_documents,
    save_network_data_artifacts,
)


def _save_json(payload: Dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    print(f"Saved artifact: {output_path}")


def _save_csv_rows(rows: List[Dict[str, Any]], output_path: Path, fieldnames: List[str] | None = None) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        fields = fieldnames or []
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            if fields:
                writer.writeheader()
        print(f"Saved artifact: {output_path}")
        return

    fields = fieldnames or sorted({k for row in rows for k in row.keys()})
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved artifact: {output_path}")


def _save_status_map_csv(status_map: Dict[str, Dict[str, int]], output_path: Path, index_name: str) -> None:
    all_statuses = sorted({status for values in status_map.values() for status in values.keys()})
    rows: List[Dict[str, Any]] = []
    for index_value in sorted(status_map.keys()):
        row: Dict[str, Any] = {index_name: index_value}
        for status in all_statuses:
            row[status] = status_map[index_value].get(status, 0)
        rows.append(row)
    _save_csv_rows(rows, output_path, fieldnames=[index_name] + all_statuses)


def _save_react_ready_exports(
    postprocess_root: Path,
    stichtag: str,
    network_data: Dict[str, Any],
    authorship_payload: Dict[str, Any],
    classification_payload: Dict[str, Any],
    conformity_metrics: Dict[str, Any],
) -> Dict[str, Path]:
    react_root = postprocess_root / stichtag / "react"

    flat_nodes: List[Dict[str, Any]] = []
    for node in network_data.get("nodes", []):
        author_value = node.get("author")
        if isinstance(author_value, list):
            author_value = " | ".join(str(a) for a in author_value)
        flat_nodes.append(
            {
                "id": node.get("id"),
                "layer": node.get("layer"),
                "status": node.get("status"),
                "type": node.get("type"),
                "created": node.get("created"),
                "compliance_score": node.get("compliance_score"),
                "author": author_value,
            }
        )

    flat_edges: List[Dict[str, Any]] = []
    for link_type, links in network_data.get("links", {}).items():
        if link_type == "explicit_dependencies" and isinstance(links, dict):
            for subtype, subtype_links in links.items():
                for link in subtype_links:
                    flat_edges.append(
                        {
                            "edge_type": subtype,
                            "source": link.get("source"),
                            "target": link.get("target"),
                            "value": link.get("value", 1),
                        }
                    )
            continue

        for link in links:
            flat_edges.append(
                {
                    "edge_type": link_type,
                    "source": link.get("source"),
                    "target": link.get("target"),
                    "value": link.get("value", 1),
                }
            )

    layer_status_long: List[Dict[str, Any]] = []
    for layer, statuses in classification_payload.get("status_distribution_by_layer", {}).items():
        for status, count in statuses.items():
            layer_status_long.append(
                {
                    "layer": layer,
                    "status": status,
                    "count": count,
                }
            )

    status_over_time_long: List[Dict[str, Any]] = []
    for year, statuses in classification_payload.get("status_over_time", {}).items():
        for status, count in statuses.items():
            status_over_time_long.append(
                {
                    "year": year,
                    "status": status,
                    "count": count,
                }
            )

    nodes_csv = react_root / "network_nodes.csv"
    edges_csv = react_root / "network_edges.csv"
    top_authors_csv = react_root / "top_authors.csv"
    sankey_grouped_csv = react_root / "sankey_grouped_links.csv"
    status_by_layer_csv = react_root / "status_by_layer_long.csv"
    status_over_time_csv = react_root / "status_over_time_long.csv"
    conformity_csv = react_root / "conformity_per_proposal.csv"

    _save_csv_rows(
        flat_nodes,
        nodes_csv,
        fieldnames=["id", "layer", "status", "type", "created", "compliance_score", "author"],
    )
    _save_csv_rows(
        flat_edges,
        edges_csv,
        fieldnames=["edge_type", "source", "target", "value"],
    )
    _save_csv_rows(
        authorship_payload.get("top_authors", []),
        top_authors_csv,
        fieldnames=["author", "count"],
    )
    _save_csv_rows(
        classification_payload.get("sankey_grouped", {}).get("links", []),
        sankey_grouped_csv,
        fieldnames=["source", "target", "count"],
    )
    _save_csv_rows(
        layer_status_long,
        status_by_layer_csv,
        fieldnames=["layer", "status", "count"],
    )
    _save_csv_rows(
        status_over_time_long,
        status_over_time_csv,
        fieldnames=["year", "status", "count"],
    )
    _save_csv_rows(
        conformity_metrics.get("per_proposal", []),
        conformity_csv,
        fieldnames=["id", "status", "compliance_score"],
    )

    index_json = react_root / "dataset_index.json"
    _save_json(
        {
            "stichtag": stichtag,
            "files": {
                "network_nodes": nodes_csv.name,
                "network_edges": edges_csv.name,
                "top_authors": top_authors_csv.name,
                "sankey_grouped_links": sankey_grouped_csv.name,
                "status_by_layer_long": status_by_layer_csv.name,
                "status_over_time_long": status_over_time_csv.name,
                "conformity_per_proposal": conformity_csv.name,
            },
        },
        index_json,
    )

    return {
        "react_nodes_csv": nodes_csv,
        "react_edges_csv": edges_csv,
        "react_top_authors_csv": top_authors_csv,
        "react_sankey_grouped_csv": sankey_grouped_csv,
        "react_status_by_layer_csv": status_by_layer_csv,
        "react_status_over_time_csv": status_over_time_csv,
        "react_conformity_csv": conformity_csv,
        "react_index_json": index_json,
    }


def prepare_ecosystem_artifacts(
    proposal_json_dir: Path,
    artifact_root: Path,
    postprocess_root: Path | None,
    stichtag: str,
    id_field: str,
    proposal_label: str,
) -> Dict[str, Path]:
    proposal_data: List[Dict[str, Any]] = load_proposal_json_documents(proposal_json_dir)

    network_data = build_network_data(
        proposal_data,
        id_field=id_field,
        proposal_label=proposal_label,
    )
    snapshot_root = artifact_root / stichtag

    network_stem = snapshot_root / "dependencies" / "network_data"
    save_network_data_artifacts(network_data, network_stem)

    authorship_metrics = extract_authorship_metrics(network_data.get("nodes", []))
    authorship_path = snapshot_root / "authorship" / "authorship_metrics.json"
    _save_json(authorship_metrics, authorship_path)
    _save_csv_rows(
        authorship_metrics.get("top_authors", []),
        snapshot_root / "authorship" / "top_authors.csv",
        fieldnames=["author", "count"],
    )
    _save_csv_rows(
        authorship_metrics.get("proposals_per_year", []),
        snapshot_root / "authorship" / "proposals_per_year.csv",
        fieldnames=["year", "count"],
    )
    _save_csv_rows(
        authorship_metrics.get("author_contribution_histogram", []),
        snapshot_root / "authorship" / "author_contribution_histogram.csv",
        fieldnames=["bips_written", "authors"],
    )

    authorship_payload = prepare_authorship_payload(network_data)
    authorship_payload_path = snapshot_root / "authorship" / "authorship_payload.json"
    _save_json(authorship_payload, authorship_payload_path)
    _save_csv_rows(
        authorship_payload.get("collaboration_centrality", []),
        snapshot_root / "authorship" / "collaboration_centrality.csv",
        fieldnames=["author", "degree", "betweenness", "closeness", "eigenvector"],
    )

    classification_payload = prepare_classification_payload(network_data)
    classification_payload_path = snapshot_root / "classification" / "classification_payload.json"
    _save_json(classification_payload, classification_payload_path)
    _save_csv_rows(
        classification_payload.get("sankey_grouped", {}).get("links", []),
        snapshot_root / "classification" / "sankey_grouped_links.csv",
        fieldnames=["source", "target", "count"],
    )
    _save_status_map_csv(
        classification_payload.get("status_distribution_by_layer", {}),
        snapshot_root / "classification" / "status_distribution_by_layer.csv",
        index_name="layer",
    )
    _save_status_map_csv(
        classification_payload.get("status_over_time", {}),
        snapshot_root / "classification" / "status_over_time.csv",
        index_name="year",
    )

    conformity_metrics = extract_conformity_metrics(proposal_data, id_field=id_field)
    conformity_path = snapshot_root / "conformity" / "conformity_metrics.json"
    _save_json(conformity_metrics, conformity_path)
    _save_csv_rows(
        conformity_metrics.get("per_proposal", []),
        snapshot_root / "conformity" / "per_proposal.csv",
        fieldnames=["id", "status", "compliance_score"],
    )
    _save_csv_rows(
        conformity_metrics.get("score_distribution", []),
        snapshot_root / "conformity" / "score_distribution.csv",
        fieldnames=["bucket", "count"],
    )
    _save_csv_rows(
        [
            {"status": status, "average_score": score}
            for status, score in conformity_metrics.get("average_score_by_status", {}).items()
        ],
        snapshot_root / "conformity" / "average_score_by_status.csv",
        fieldnames=["status", "average_score"],
    )

    saved_paths: Dict[str, Path] = {
        "network_json": network_stem.with_suffix(".json"),
        "authorship_json": authorship_path,
        "authorship_payload_json": authorship_payload_path,
        "classification_json": classification_payload_path,
        "conformity_json": conformity_path,
    }

    if postprocess_root is not None:
        saved_paths.update(
            _save_react_ready_exports(
                postprocess_root=postprocess_root,
                stichtag=stichtag,
                network_data=network_data,
                authorship_payload=authorship_payload,
                classification_payload=classification_payload,
                conformity_metrics=conformity_metrics,
            )
        )

    return saved_paths
