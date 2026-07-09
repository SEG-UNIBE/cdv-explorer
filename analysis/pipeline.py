import csv
import json
from collections.abc import Iterable, Mapping, Sequence
from itertools import combinations
from pathlib import Path
from typing import Any

from analysis.authorship import extract_authorship_metrics, prepare_authorship_payload
from analysis.classification import prepare_classification_payload
from analysis.conformity import extract_conformity_metrics
from analysis.dependencies import (
    available_llm_model_entries,
    build_network_data,
    collapse_network_data_to_llm_model,
    extract_dependency_metrics,
    load_proposal_json_documents,
    save_network_data_artifacts,
)
from analysis.dependencies.network import normalize_dependency_edges
from analysis.evolution import prepare_evolution_payload
from analysis.wordcloud import extract_wordcloud_metrics
from pipeline.source_context import SourceContext


def _save_json(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _load_json(input_path: Path) -> dict[str, Any]:
    with input_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def combined_source_key(source_slugs: Iterable[str]) -> str:
    return "+".join(sorted(str(source_slug) for source_slug in source_slugs))


def _save_csv_rows(
    rows: list[dict[str, Any]], output_path: Path, fieldnames: list[str] | None = None
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
    status_map: dict[str, dict[str, int]], output_path: Path, index_name: str
) -> None:
    all_statuses = sorted(
        {status for values in status_map.values() for status in values.keys()}
    )
    rows: list[dict[str, Any]] = []
    for index_value in sorted(status_map.keys()):
        row: dict[str, Any] = {index_name: index_value}
        for status in all_statuses:
            row[status] = status_map[index_value].get(status, 0)
        rows.append(row)
    _save_csv_rows(rows, output_path, fieldnames=[index_name] + all_statuses)


def _known_proposal_ids_by_source(
    context: SourceContext, snapshot: str
) -> dict[str, set[str]]:
    ids_by_source: dict[str, set[str]] = {}

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
) -> dict[str, Any]:
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
    networks_by_source: Sequence[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    reviewed_ips: list[dict[str, Any]] = []
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
        Path(str(source_config["postprocess"]))
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
) -> dict[str, dict[str, Path]]:
    selected_source_slugs = sorted(source_slugs or source_configs.keys())
    saved: dict[str, dict[str, Path]] = {}

    def emit(message: str, advance: int = 0) -> None:
        if progress_callback is not None:
            progress_callback(message, advance)

    for size in range(2, len(selected_source_slugs) + 1):
        for combo in combinations(selected_source_slugs, size):
            combo_key = combined_source_key(combo)
            emit(f"{combo_key}: loading source network artifacts")
            networks_by_source: list[tuple[str, dict[str, Any]]] = []
            missing_paths: list[Path] = []
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
            save_network_data_artifacts(network_data, network_stem, include_json=False)

            emit(f"{combo_key}: recomputing dependency metrics", advance=1)
            dependency_metrics = extract_dependency_metrics(network_data)

            emit(f"{combo_key}: preparing authorship artifacts", advance=1)
            authorship_metrics = extract_authorship_metrics(
                network_data.get("nodes", [])
            )
            authorship_path = snapshot_root / "authorship" / "authorship_metrics.json"
            _save_json(authorship_metrics, authorship_path)
            authorship_payload = prepare_authorship_payload(network_data)

            emit(
                f"{combo_key}: preparing non-mergeable section placeholders", advance=1
            )
            classification_payload = _combined_placeholder_payload(
                snapshot, combo_key, combo, "classification"
            )
            evolution_payload = _combined_placeholder_payload(
                snapshot, combo_key, combo, "evolution"
            )
            conformity_metrics = _combined_placeholder_payload(
                snapshot, combo_key, combo, "conformity"
            )

            emit(f"{combo_key}: writing frontend payloads", advance=1)
            payload_paths = _save_frontend_payloads(
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
                "network_json": payload_paths["payload_network_data_json"],
                "dependency_metrics_json": payload_paths[
                    "payload_dependency_metrics_json"
                ],
                "authorship_json": authorship_path,
                "authorship_payload_json": payload_paths[
                    "payload_authorship_payload_json"
                ],
                "classification_json": payload_paths[
                    "payload_classification_payload_json"
                ],
                "evolution_json": payload_paths["payload_evolution_payload_json"],
                "conformity_json": payload_paths["payload_conformity_metrics_json"],
                **payload_paths,
            }
            emit(f"{combo_key}: completed", advance=1)

    return saved


def _flatten_conformity_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def _trim_conformity_checks(conformity_metrics: dict[str, Any]) -> dict[str, Any]:
    """Drop per-check data the dashboard never renders from the payload.

    The conformity views only list *failed* checks (failed-checks histogram and
    swarm-plot tooltips) and read id/label/passed/details per check, so passed
    and skipped check entries are omitted entirely. The per-standard counters
    (passed_checks/failed_checks/skipped_checks) keep the aggregate view intact.
    Full check results are reproducible via the pipeline from Stage II data.
    """
    trimmed = dict(conformity_metrics)
    per_proposal: list[dict[str, Any]] = []
    for row in conformity_metrics.get("per_proposal") or []:
        row = dict(row)
        compliance = row.get("formal_compliance")
        if isinstance(compliance, dict):
            compliance = dict(compliance)
            for standard_key, standard in compliance.items():
                if not isinstance(standard, dict) or "checks" not in standard:
                    continue
                standard = dict(standard)
                standard["checks"] = [
                    {
                        "id": check.get("id"),
                        "label": check.get("label"),
                        "passed": False,
                        "details": check.get("details"),
                    }
                    for check in standard.get("checks") or []
                    if check.get("passed") is False
                ]
                compliance[standard_key] = standard
            row["formal_compliance"] = compliance
        per_proposal.append(row)
    trimmed["per_proposal"] = per_proposal
    return trimmed


# Relative payload locations inside 04_postprocess/<snapshot>/ — the frontend
# fetch contract (mirrored by react/src/data.js and react/scripts/syncPublicData.js).
FRONTEND_PAYLOAD_FILES: dict[str, str] = {
    "network_data": "dependencies/network_data.json",
    "dependency_metrics": "dependencies/dependency_metrics.json",
    "authorship_payload": "authorship/authorship_payload.json",
    "classification_payload": "classification/classification_payload.json",
    "evolution_payload": "evolution/evolution_payload.json",
    "conformity_metrics": "conformity/conformity_metrics.json",
}


def _save_frontend_payloads(
    postprocess_root: Path,
    snapshot: str,
    network_data: dict[str, Any],
    dependency_metrics: dict[str, Any],
    authorship_payload: dict[str, Any],
    classification_payload: dict[str, Any],
    evolution_payload: dict[str, Any],
    conformity_metrics: dict[str, Any],
) -> dict[str, Path]:
    payload_root = postprocess_root / snapshot
    payloads: dict[str, dict[str, Any]] = {
        "network_data": network_data,
        "dependency_metrics": dependency_metrics,
        "authorship_payload": authorship_payload,
        "classification_payload": classification_payload,
        "evolution_payload": evolution_payload,
        "conformity_metrics": _trim_conformity_checks(conformity_metrics),
    }

    saved: dict[str, Path] = {}
    for name, rel_path in FRONTEND_PAYLOAD_FILES.items():
        payload_path = payload_root / rel_path
        _save_json(payloads[name], payload_path)
        saved[f"payload_{name}_json"] = payload_path

    index_json = payload_root / "dataset_index.json"
    _save_json(
        {"snapshot": snapshot, "files": dict(FRONTEND_PAYLOAD_FILES)},
        index_json,
    )
    saved["payload_index_json"] = index_json
    return saved


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
) -> dict[str, Path]:
    context = source_context or SourceContext.default()

    def emit(message: str, advance: int = 0) -> None:
        if progress_callback is not None:
            progress_callback(message, advance)
            return
        if status_callback is not None:
            status_callback(message)

    emit("Loading proposal JSON")
    proposal_data: list[dict[str, Any]] = load_proposal_json_documents(
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

    if postprocess_root is None:
        raise ValueError(
            "postprocess_root is required: frontend payloads are written to "
            "04_postprocess as the canonical Stage IV output."
        )

    snapshot_root = artifact_root / snapshot

    network_stem = snapshot_root / "dependencies" / "network_data"
    save_network_data_artifacts(network_data, network_stem, include_json=False)

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
    _save_csv_rows(
        authorship_payload.get("collaboration_centrality", []),
        snapshot_root / "authorship" / "collaboration_centrality.csv",
        fieldnames=["author", "degree", "betweenness", "closeness", "eigenvector"],
    )

    emit("Preparing dependency metrics artifacts", advance=1)
    dependency_metrics = extract_dependency_metrics(network_data)

    emit("Preparing classification artifacts", advance=1)
    classification_payload = prepare_classification_payload(
        network_data, source_context=context
    )
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

    emit("Preparing conformity artifacts", advance=1)
    conformity_metrics = extract_conformity_metrics(
        proposal_data, id_field=id_field, source_context=context
    )
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

    saved_paths: dict[str, Path] = {
        "authorship_json": authorship_path,
        "wordcloud_json": wordcloud_path,
    }

    emit("Writing frontend payloads", advance=1)
    payload_paths = _save_frontend_payloads(
        postprocess_root=postprocess_root,
        snapshot=snapshot,
        network_data=network_data,
        dependency_metrics=dependency_metrics,
        authorship_payload=authorship_payload,
        classification_payload=classification_payload,
        evolution_payload=evolution_payload,
        conformity_metrics=conformity_metrics,
    )
    saved_paths.update(payload_paths)
    saved_paths.update(
        {
            "network_json": payload_paths["payload_network_data_json"],
            "dependency_metrics_json": payload_paths["payload_dependency_metrics_json"],
            "authorship_payload_json": payload_paths["payload_authorship_payload_json"],
            "classification_json": payload_paths["payload_classification_payload_json"],
            "evolution_json": payload_paths["payload_evolution_payload_json"],
            "conformity_json": payload_paths["payload_conformity_metrics_json"],
        }
    )
    emit("Completed", advance=1)

    return saved_paths
