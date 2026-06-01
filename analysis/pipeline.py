import json
import csv
from pathlib import Path
from typing import Any, Dict, List

from analysis.authorship import extract_authorship_metrics
from analysis.authorship import prepare_authorship_payload
from analysis.classification import prepare_classification_payload
from analysis.conformity import extract_conformity_metrics
from analysis.dependencies.constants import PREAMBLE_EXTRACTED
from analysis.dependencies import (
    build_network_data,
    extract_dependency_metrics,
    load_proposal_json_documents,
    save_network_data_artifacts,
)
from analysis.evolution import prepare_evolution_payload
from analysis.wordcloud import extract_wordcloud_metrics


def _save_json(payload: Dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _save_csv_rows(rows: List[Dict[str, Any]], output_path: Path, fieldnames: List[str] | None = None) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        fields = fieldnames or []
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            if fields:
                writer.writeheader()
        return

    fields = fieldnames or sorted({k for row in rows for k in row.keys()})
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _save_status_map_csv(status_map: Dict[str, Dict[str, int]], output_path: Path, index_name: str) -> None:
    all_statuses = sorted({status for values in status_map.values() for status in values.keys()})
    rows: List[Dict[str, Any]] = []
    for index_value in sorted(status_map.keys()):
        row: Dict[str, Any] = {index_name: index_value}
        for status in all_statuses:
            row[status] = status_map[index_value].get(status, 0)
        rows.append(row)
    _save_csv_rows(rows, output_path, fieldnames=[index_name] + all_statuses)


def _flatten_conformity_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "id": row.get("id"),
            "status": row.get("status"),
            "compliance_score": row.get("compliance_score"),
            "bip2_score": row.get("bip2_score"),
            "bip3_score": row.get("bip3_score"),
        }
        for row in rows
    ]


def _save_react_ready_exports(
    postprocess_root: Path,
    snapshot: str,
    network_data: Dict[str, Any],
    dependency_metrics: Dict[str, Any],
    authorship_payload: Dict[str, Any],
    classification_payload: Dict[str, Any],
    evolution_payload: Dict[str, Any],
    conformity_metrics: Dict[str, Any],
) -> Dict[str, Path]:
    react_root = postprocess_root / snapshot / "react"

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
        if link_type == PREAMBLE_EXTRACTED and isinstance(links, dict):
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
    status_over_time_csv = react_root / "status_over_time_long.csv"
    conformity_csv = react_root / "conformity_per_proposal.csv"
    dependency_metrics_json = react_root / "dependency_metrics.json"

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
        status_over_time_long,
        status_over_time_csv,
        fieldnames=["year", "status", "count"],
    )
    _save_csv_rows(
        _flatten_conformity_rows(conformity_metrics.get("per_proposal", [])),
        conformity_csv,
        fieldnames=["id", "status", "compliance_score", "bip2_score", "bip3_score"],
    )
    _save_json(dependency_metrics, dependency_metrics_json)

    index_json = react_root / "dataset_index.json"
    _save_json(
        {
            "snapshot": snapshot,
            "files": {
                "network_nodes": nodes_csv.name,
                "network_edges": edges_csv.name,
                "top_authors": top_authors_csv.name,
                "sankey_grouped_links": sankey_grouped_csv.name,
                "status_over_time_long": status_over_time_csv.name,
                "conformity_per_proposal": conformity_csv.name,
                "dependency_metrics": dependency_metrics_json.name,
            },
        },
        index_json,
    )

    return {
        "react_nodes_csv": nodes_csv,
        "react_edges_csv": edges_csv,
        "react_top_authors_csv": top_authors_csv,
        "react_sankey_grouped_csv": sankey_grouped_csv,
        "react_status_over_time_csv": status_over_time_csv,
        "react_conformity_csv": conformity_csv,
        "react_dependency_metrics_json": dependency_metrics_json,
        "react_index_json": index_json,
    }


def prepare_ecosystem_artifacts(
    proposal_json_dir: Path,
    artifact_root: Path,
    postprocess_root: Path | None,
    snapshot: str,
    id_field: str,
    proposal_label: str,
    repo_dir: Path | None = None,
    file_prefix: str = "bip",
    status_callback=None,
    progress_callback=None,
) -> Dict[str, Path]:
    def emit(message: str, advance: int = 0) -> None:
        if progress_callback is not None:
            progress_callback(message, advance)
            return
        if status_callback is not None:
            status_callback(message)

    emit("Loading proposal JSON")
    proposal_data: List[Dict[str, Any]] = load_proposal_json_documents(proposal_json_dir)

    emit("Building dependency network", advance=1)
    network_data = build_network_data(
        proposal_data,
        id_field=id_field,
        proposal_label=proposal_label,
    )
    snapshot_root = artifact_root / snapshot

    network_stem = snapshot_root / "dependencies" / "network_data"
    save_network_data_artifacts(network_data, network_stem)

    emit("Preparing authorship artifacts", advance=1)
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

    emit("Preparing dependency metrics artifacts", advance=1)
    dependency_metrics = extract_dependency_metrics(network_data)
    dependency_metrics_path = snapshot_root / "dependencies" / "dependency_metrics.json"
    _save_json(dependency_metrics, dependency_metrics_path)

    emit("Preparing classification artifacts", advance=1)
    classification_payload = prepare_classification_payload(network_data)
    classification_payload_path = snapshot_root / "classification" / "classification_payload.json"
    _save_json(classification_payload, classification_payload_path)
    _save_csv_rows(
        classification_payload.get("sankey_grouped", {}).get("links", []),
        snapshot_root / "classification" / "sankey_grouped_links.csv",
        fieldnames=["source", "target", "count"],
    )
    _save_status_map_csv(
        classification_payload.get("status_over_time", {}),
        snapshot_root / "classification" / "status_over_time.csv",
        index_name="year",
    )

    emit("Preparing evolution artifacts", advance=1)
    evolution_payload = prepare_evolution_payload(
        proposal_data,
        snapshot_label=snapshot,
        id_field=id_field,
        repo_dir=repo_dir,
        file_prefix=file_prefix,
    )
    evolution_payload_path = snapshot_root / "evolution" / "evolution_payload.json"
    _save_json(evolution_payload, evolution_payload_path)

    emit("Preparing conformity artifacts", advance=1)
    conformity_metrics = extract_conformity_metrics(proposal_data, id_field=id_field)
    conformity_path = snapshot_root / "conformity" / "conformity_metrics.json"
    _save_json(conformity_metrics, conformity_path)
    _save_csv_rows(
        _flatten_conformity_rows(conformity_metrics.get("per_proposal", [])),
        snapshot_root / "conformity" / "per_proposal.csv",
        fieldnames=["id", "status", "compliance_score", "bip2_score", "bip3_score"],
    )
    emit("Preparing wordcloud artifacts", advance=1)
    wordcloud_metrics = extract_wordcloud_metrics(proposal_data, id_field=id_field)
    wordcloud_path = snapshot_root / "wordcloud" / "wordcloud_metrics.json"
    _save_json(wordcloud_metrics, wordcloud_path)
    _save_csv_rows(
        wordcloud_metrics.get("top_words", []),
        snapshot_root / "wordcloud" / "top_words.csv",
        fieldnames=["word", "count"],
    )
    _save_csv_rows(
        wordcloud_metrics.get("per_proposal", []),
        snapshot_root / "wordcloud" / "per_proposal.csv",
        fieldnames=["id", "unique_terms", "total_terms"],
    )

    saved_paths: Dict[str, Path] = {
        "network_json": network_stem.with_suffix(".json"),
        "dependency_metrics_json": dependency_metrics_path,
        "authorship_json": authorship_path,
        "authorship_payload_json": authorship_payload_path,
        "classification_json": classification_payload_path,
        "evolution_json": evolution_payload_path,
        "conformity_json": conformity_path,
        "wordcloud_json": wordcloud_path,
    }

    if postprocess_root is not None:
        emit("Writing react exports", advance=1)
        saved_paths.update(
            _save_react_ready_exports(
                postprocess_root=postprocess_root,
                snapshot=snapshot,
                network_data=network_data,
                dependency_metrics=dependency_metrics,
                authorship_payload=authorship_payload,
                classification_payload=classification_payload,
                evolution_payload=evolution_payload,
                conformity_metrics=conformity_metrics,
            )
        )
        emit("Completed", advance=1)
    else:
        emit("Completed", advance=2)

    return saved_paths
