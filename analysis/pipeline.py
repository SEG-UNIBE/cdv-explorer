import json
import csv
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from analysis.authorship import extract_authorship_metrics
from analysis.authorship import prepare_authorship_payload
from analysis.classification import prepare_classification_payload
from analysis.conformity import extract_conformity_metrics
from analysis.dependencies import (
    build_network_data,
    collapse_network_data_to_llm_model,
    available_llm_model_entries,
    extract_dependency_metrics,
    load_proposal_json_documents,
    save_network_data_artifacts,
)
from analysis.dependencies.network import normalize_dependency_edges
from analysis.evolution import prepare_evolution_payload
from analysis.wordcloud import extract_wordcloud_metrics
from pipeline.source_context import SourceContext


def _save_json(payload: Dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _load_json(input_path: Path) -> Dict[str, Any]:
    with input_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def combined_source_key(source_slugs: Iterable[str]) -> str:
    return "+".join(sorted(str(source_slug) for source_slug in source_slugs))


def _save_csv_rows(
    rows: List[Dict[str, Any]], output_path: Path, fieldnames: List[str] | None = None
) -> None:
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


def _save_status_map_csv(
    status_map: Dict[str, Dict[str, int]], output_path: Path, index_name: str
) -> None:
    all_statuses = sorted(
        {status for values in status_map.values() for status in values.keys()}
    )
    rows: List[Dict[str, Any]] = []
    for index_value in sorted(status_map.keys()):
        row: Dict[str, Any] = {index_name: index_value}
        for status in all_statuses:
            row[status] = status_map[index_value].get(status, 0)
        rows.append(row)
    _save_csv_rows(rows, output_path, fieldnames=[index_name] + all_statuses)


def _known_proposal_ids_by_source(
    context: SourceContext, snapshot: str
) -> Dict[str, set[str]]:
    ids_by_source: Dict[str, set[str]] = {}

    for source_slug, source_config in context.ecosystem_source_configs.items():
        preprocess_root = source_config.get("preprocess")
        id_field = source_config.get("primary_id_field")
        if not preprocess_root or not id_field:
            continue

        source_context = SourceContext.from_config(
            source_config,
            ecosystem_slug=context.ecosystem_slug,
            source_slug=source_slug,
        )
        source_dir = Path(preprocess_root) / snapshot
        if not source_dir.is_dir():
            continue

        ids: set[str] = set()
        for document in load_proposal_json_documents(
            source_dir, source_context=source_context
        ):
            proposal_id = document.get("raw", {}).get("preamble", {}).get(id_field)
            if proposal_id is not None:
                ids.add(str(proposal_id))
        ids_by_source[source_slug] = ids

    return ids_by_source


def _combined_placeholder_payload(
    snapshot: str,
    combo_key: str,
    source_slugs: Sequence[str],
    section: str,
) -> Dict[str, Any]:
    meta = {
        "snapshot": snapshot,
        "source_slugs": list(source_slugs),
        "combination_key": combo_key,
        "merge_status": "not_mergeable",
        "section": section,
    }
    if section == "classification":
        return {"meta": meta, "sankey_grouped": {"links": []}, "status_over_time": {}}
    if section == "evolution":
        return {
            "meta": meta,
            "status_evolution": {"categories": [], "rows": []},
            "proposal_timelines": [],
        }
    if section == "conformity":
        return {"meta": meta, "per_proposal": []}
    return {"meta": meta}


def _node_graph_key(node: Mapping[str, Any], source_slug: str) -> str:
    graph_key = node.get("graph_key") or node.get("graphId") or node.get("graph_id")
    if graph_key is not None:
        return str(graph_key)
    return f"{source_slug}:{node.get('id')}"


def _published_llm_model_from_network_data(
    network_data: Mapping[str, Any],
) -> str | None:
    model = str(network_data.get("llm_model") or "").strip()
    if model:
        return model
    available = [
        str(entry.get("model") or "").strip()
        for entry in available_llm_model_entries(network_data)
    ]
    available = [model_name for model_name in available if model_name]
    if len(available) == 1:
        return available[0]
    if len(available) > 1:
        raise ValueError(
            "Source artifact still exposes multiple LLM models. Rebuild source artifacts with "
            "`--artifact-llm-model <model>` before building combined-source artifacts."
        )
    return None


def merge_source_network_data(
    networks_by_source: Sequence[tuple[str, Dict[str, Any]]],
) -> Dict[str, Any]:
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    reviewed_ips: List[Dict[str, Any]] = []
    published_llm_models: set[str] = set()
    seen_nodes: set[str] = set()
    seen_reviewed_ips: set[str] = set()
    source_slugs = [source_slug for source_slug, _network_data in networks_by_source]

    for source_slug, network_data in networks_by_source:
        for node in network_data.get("nodes", []):
            if not isinstance(node, dict):
                continue
            graph_key = _node_graph_key(node, source_slug)
            if graph_key in seen_nodes:
                continue
            seen_nodes.add(graph_key)
            nodes.append(
                {
                    **node,
                    "graph_key": graph_key,
                    "source_slug": source_slug,
                }
            )

        edges.extend(normalize_dependency_edges(network_data))
        published_model = _published_llm_model_from_network_data(network_data)
        if published_model:
            published_llm_models.add(published_model)
        for reviewed_ip in network_data.get("ground_truth_reviewed_ips", []):
            if not isinstance(reviewed_ip, dict):
                continue
            graph_key = str(reviewed_ip.get("ip") or "").strip()
            if not graph_key or graph_key in seen_reviewed_ips:
                continue
            seen_reviewed_ips.add(graph_key)
            reviewed_ips.append(reviewed_ip)

    if len(published_llm_models) > 1:
        raise ValueError(
            "Cannot build combined-source artifacts from mixed published LLM models: "
            f"{', '.join(sorted(published_llm_models))}. Rebuild the selected sources with the same "
            "`--artifact-llm-model` value."
        )

    return {
        "nodes": nodes,
        "dependency_edges": edges,
        **(
            {"llm_model": next(iter(published_llm_models))}
            if published_llm_models
            else {}
        ),
        "ground_truth_reviewed_ips": reviewed_ips,
        "meta": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "source_slugs": source_slugs,
            "is_combined_source": True,
            "combination_key": combined_source_key(source_slugs),
        },
    }


def _combined_artifact_roots(ecosystem_slug: str, combo_key: str) -> tuple[Path, Path]:
    combo_root = Path("ip_data") / ecosystem_slug / "_combined" / combo_key
    return combo_root / "03_analysis", combo_root / "04_postprocess"


def _source_network_path(source_config: Mapping[str, Any], snapshot: str) -> Path:
    return (
        Path(str(source_config["analysis"]))
        / snapshot
        / "dependencies"
        / "network_data.json"
    )


def prepare_combined_source_artifacts(
    ecosystem_slug: str,
    source_configs: Mapping[str, Mapping[str, Any]],
    snapshot: str,
    source_slugs: Sequence[str] | None = None,
    progress_callback=None,
) -> Dict[str, Dict[str, Path]]:
    selected_source_slugs = sorted(source_slugs or source_configs.keys())
    saved: Dict[str, Dict[str, Path]] = {}

    def emit(message: str, advance: int = 0) -> None:
        if progress_callback is not None:
            progress_callback(message, advance)

    for size in range(2, len(selected_source_slugs) + 1):
        for combo in combinations(selected_source_slugs, size):
            combo_key = combined_source_key(combo)
            emit(f"{combo_key}: loading source network artifacts")
            networks_by_source: List[tuple[str, Dict[str, Any]]] = []
            missing_paths: List[Path] = []
            for source_slug in combo:
                network_path = _source_network_path(
                    source_configs[source_slug], snapshot
                )
                if not network_path.exists():
                    missing_paths.append(network_path)
                    continue
                networks_by_source.append((source_slug, _load_json(network_path)))

            if missing_paths:
                raise FileNotFoundError(
                    f"Cannot build combined artifacts for {ecosystem_slug}/{combo_key}/{snapshot}; "
                    f"missing: {', '.join(str(path) for path in missing_paths)}"
                )

            analysis_root, postprocess_root = _combined_artifact_roots(
                ecosystem_slug, combo_key
            )
            snapshot_root = analysis_root / snapshot

            emit(f"{combo_key}: merging dependency network", advance=1)
            network_data = merge_source_network_data(networks_by_source)
            network_stem = snapshot_root / "dependencies" / "network_data"
            save_network_data_artifacts(network_data, network_stem)

            emit(f"{combo_key}: recomputing dependency metrics", advance=1)
            dependency_metrics = extract_dependency_metrics(network_data)
            dependency_metrics_path = (
                snapshot_root / "dependencies" / "dependency_metrics.json"
            )
            _save_json(dependency_metrics, dependency_metrics_path)

            emit(f"{combo_key}: preparing authorship artifacts", advance=1)
            authorship_metrics = extract_authorship_metrics(
                network_data.get("nodes", [])
            )
            authorship_path = snapshot_root / "authorship" / "authorship_metrics.json"
            _save_json(authorship_metrics, authorship_path)
            authorship_payload = prepare_authorship_payload(network_data)
            authorship_payload_path = (
                snapshot_root / "authorship" / "authorship_payload.json"
            )
            _save_json(authorship_payload, authorship_payload_path)

            classification_payload = _combined_placeholder_payload(
                snapshot, combo_key, combo, "classification"
            )
            evolution_payload = _combined_placeholder_payload(
                snapshot, combo_key, combo, "evolution"
            )
            conformity_metrics = _combined_placeholder_payload(
                snapshot, combo_key, combo, "conformity"
            )

            emit(f"{combo_key}: writing non-mergeable section placeholders", advance=1)
            classification_path = (
                snapshot_root / "classification" / "classification_payload.json"
            )
            evolution_path = snapshot_root / "evolution" / "evolution_payload.json"
            conformity_path = snapshot_root / "conformity" / "conformity_metrics.json"
            _save_json(classification_payload, classification_path)
            _save_json(evolution_payload, evolution_path)
            _save_json(conformity_metrics, conformity_path)

            emit(f"{combo_key}: writing react exports", advance=1)
            react_paths = _save_react_ready_exports(
                postprocess_root=postprocess_root,
                snapshot=snapshot,
                network_data=network_data,
                dependency_metrics=dependency_metrics,
                authorship_payload=authorship_payload,
                classification_payload=classification_payload,
                evolution_payload=evolution_payload,
                conformity_metrics=conformity_metrics,
            )

            saved[combo_key] = {
                "network_json": network_stem.with_suffix(".json"),
                "dependency_metrics_json": dependency_metrics_path,
                "authorship_json": authorship_path,
                "authorship_payload_json": authorship_payload_path,
                "classification_json": classification_path,
                "evolution_json": evolution_path,
                "conformity_json": conformity_path,
                **react_paths,
            }
            emit(f"{combo_key}: completed", advance=1)

    return saved


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
    for edge in network_data.get("dependency_edges", []):
        flat_edges.append(
            {
                "source": edge.get("source"),
                "target": edge.get("target"),
                "extraction_method": edge.get("extraction_method"),
                "relation_type": edge.get("relation_type"),
                "value": edge.get("value", 1),
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
        fieldnames=[
            "id",
            "layer",
            "status",
            "type",
            "created",
            "compliance_score",
            "author",
        ],
    )
    _save_csv_rows(
        flat_edges,
        edges_csv,
        fieldnames=["source", "target", "extraction_method", "relation_type", "value"],
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
    source_context: SourceContext | None = None,
    artifact_llm_model: str | None = None,
    status_callback=None,
    progress_callback=None,
) -> Dict[str, Path]:
    context = source_context or SourceContext.default()

    def emit(message: str, advance: int = 0) -> None:
        if progress_callback is not None:
            progress_callback(message, advance)
            return
        if status_callback is not None:
            status_callback(message)

    emit("Loading proposal JSON")
    proposal_data: List[Dict[str, Any]] = load_proposal_json_documents(
        proposal_json_dir,
        source_context=context,
    )

    emit("Building dependency network", advance=1)
    network_data = build_network_data(
        proposal_data,
        id_field=id_field,
        proposal_label=proposal_label,
        source_context=context,
        known_proposal_ids_by_source=_known_proposal_ids_by_source(context, snapshot),
    )
    available_llm_models = [
        str(entry.get("model") or "").strip()
        for entry in available_llm_model_entries(network_data)
        if str(entry.get("model") or "").strip()
    ]
    if artifact_llm_model:
        network_data = collapse_network_data_to_llm_model(
            network_data, artifact_llm_model
        )
    elif len(available_llm_models) == 1:
        network_data = collapse_network_data_to_llm_model(
            network_data, available_llm_models[0]
        )
    elif len(available_llm_models) > 1:
        raise ValueError(
            "Multiple LLM models are present in the preprocessed data for "
            f"{context.ecosystem_slug}/{context.source_slug}/{snapshot}: {', '.join(sorted(available_llm_models))}. "
            "Re-run with `--artifact-llm-model <model>` to choose which model should be published into the web artifacts."
        )
    else:
        network_data = collapse_network_data_to_llm_model(network_data, None)

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
    classification_payload = prepare_classification_payload(
        network_data, source_context=context
    )
    classification_payload_path = (
        snapshot_root / "classification" / "classification_payload.json"
    )
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
        source_context=context,
    )
    evolution_payload_path = snapshot_root / "evolution" / "evolution_payload.json"
    _save_json(evolution_payload, evolution_payload_path)

    emit("Preparing conformity artifacts", advance=1)
    conformity_metrics = extract_conformity_metrics(
        proposal_data, id_field=id_field, source_context=context
    )
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
