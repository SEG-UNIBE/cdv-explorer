from __future__ import annotations

import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

from analysis.dependencies.constants import GROUND_TRUTH_CURATED
from analysis.validation.ground_truth import (
    REVIEWED_IPS_CSV_COLUMNS,
    load_ground_truth_ips,
)

ALL_METHODS = "all_methods"
REGEX_ONLY = "regex_only"
LLM_ONLY = "llm_only"
PREAMBLE_ONLY = "preamble_only"

DENSITY_BASIS_OPTIONS = {
    ALL_METHODS: {"body_extracted_regex", "body_extracted_llm", "preamble_extracted"},
    REGEX_ONLY: {"body_extracted_regex"},
    LLM_ONLY: {"body_extracted_llm"},
    PREAMBLE_ONLY: {"preamble_extracted"},
}


def _graph_key_sort_parts(value: Any) -> tuple[str, int, str]:
    text = str(value or "").strip()
    if ":" not in text:
        return ("", 1_000_000_000, text)
    source_slug, proposal_id = text.split(":", 1)
    try:
        return (source_slug, int(proposal_id), proposal_id)
    except ValueError:
        return (source_slug, 1_000_000_000, proposal_id)


def _load_network_data(network_path: Path) -> Dict[str, Any]:
    with network_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"`{network_path}` must contain a JSON object")
    return payload


def _era_labels(count: int) -> List[str]:
    if count <= 1:
        return ["all"]
    if count == 2:
        return ["early", "recent"]
    if count == 3:
        return ["early", "middle", "recent"]
    return [f"era_{index + 1}" for index in range(count)]


def _assign_era_buckets(candidates: List[Dict[str, Any]], era_bucket_count: int) -> None:
    labels = _era_labels(era_bucket_count)
    dated = [
        (index, str(candidate.get("created") or ""))
        for index, candidate in enumerate(candidates)
        if str(candidate.get("created") or "").strip()
    ]
    dated.sort(key=lambda item: (item[1], str(candidates[item[0]].get("ip") or "")))

    if not dated:
        for candidate in candidates:
            candidate["era_bucket"] = "unknown"
        return

    total = len(dated)
    for rank, (index, _created) in enumerate(dated):
        bucket_index = min((rank * len(labels)) // total, len(labels) - 1)
        candidates[index]["era_bucket"] = labels[bucket_index]

    for candidate in candidates:
        candidate.setdefault("era_bucket", "unknown")


def _density_bucket(count: int, low_max: int) -> str:
    if count <= 0:
        return "none"
    if count <= low_max:
        return "low"
    return "high"


def _sample_candidates(
    candidates: Sequence[Dict[str, Any]],
    *,
    count: int,
    seed: int,
) -> List[Dict[str, Any]]:
    if count <= 0:
        return []

    rng = random.Random(seed)
    strata: dict[tuple[str, str], list[Dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        strata[(str(candidate.get("era_bucket") or "unknown"), str(candidate.get("density_bucket") or "unknown"))].append(dict(candidate))

    ordered_strata = sorted(strata)
    for rows in strata.values():
        rng.shuffle(rows)

    sample: List[Dict[str, Any]] = []
    while len(sample) < count:
        progressed = False
        for key in ordered_strata:
            rows = strata[key]
            if not rows:
                continue
            sample.append(rows.pop())
            progressed = True
            if len(sample) >= count:
                break
        if not progressed:
            break

    return sample


def build_reviewed_ip_sample(
    network_data: Mapping[str, Any],
    *,
    source_slug: str,
    count: int,
    seed: int,
    era_bucket_count: int = 3,
    density_low_max: int = 2,
    density_basis: str = ALL_METHODS,
    proposal_type: str | None = None,
    exclude_ips: Sequence[str] | None = None,
) -> List[Dict[str, Any]]:
    nodes = network_data.get("nodes", [])
    edges = network_data.get("dependency_edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("network_data must contain `nodes` and `dependency_edges` arrays")

    exclude = {str(value).strip() for value in (exclude_ips or []) if str(value).strip()}
    allowed_methods = DENSITY_BASIS_OPTIONS.get(density_basis)
    if not allowed_methods:
        raise ValueError(f"Unknown density basis `{density_basis}`")
    outgoing_targets: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        if not isinstance(edge, Mapping):
            continue
        extraction_method = str(edge.get("extraction_method") or "")
        if extraction_method == GROUND_TRUTH_CURATED or extraction_method not in allowed_methods:
            continue
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        if not source or not target or not source.startswith(f"{source_slug}:"):
            continue
        outgoing_targets[source].add(target)

    candidates: List[Dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        proposal_id = str(node.get("id") or "").strip()
        if not proposal_id:
            continue
        ip = f"{source_slug}:{proposal_id}"
        if ip in exclude:
            continue
        node_type = str(node.get("type") or "").strip()
        if proposal_type and node_type != proposal_type:
            continue
        extracted_target_count = len(outgoing_targets.get(ip, set()))
        candidates.append({
            "ip": ip,
            "created": str(node.get("created") or "").strip(),
            "status": str(node.get("status") or "").strip(),
            "type": node_type,
            "layer": str(node.get("layer") or "").strip(),
            "title": str(node.get("title") or "").strip(),
            "extracted_target_count": extracted_target_count,
            "density_bucket": _density_bucket(extracted_target_count, density_low_max),
            "density_basis": density_basis,
        })

    _assign_era_buckets(candidates, era_bucket_count)
    return _sample_candidates(candidates, count=count, seed=seed)


def write_ips_csv(rows: Sequence[Mapping[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sorted_rows = sorted(
        rows,
        key=lambda row: _graph_key_sort_parts(row.get("ip")),
    )
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(REVIEWED_IPS_CSV_COLUMNS), delimiter="\t")
        writer.writeheader()
        for row in sorted_rows:
            writer.writerow({field: row.get(field, "") for field in REVIEWED_IPS_CSV_COLUMNS})


def prefill_ips_csv(
    ecosystem_slug: str,
    *,
    source_slug: str,
    network_path: Path,
    count: int,
    seed: int,
    era_bucket_count: int = 3,
    density_low_max: int = 2,
    density_basis: str = ALL_METHODS,
    proposal_type: str | None = None,
    reviewer: str = "",
    replace: bool = False,
) -> Dict[str, Any]:
    network_data = _load_network_data(network_path)
    output_path = Path("ip_data") / ecosystem_slug / "ground_truth" / "ips.csv"
    existing_rows = [] if replace else load_ground_truth_ips(ecosystem_slug, strict=False)
    existing_ips = [str(row.get("ip") or "").strip() for row in existing_rows]

    sampled = build_reviewed_ip_sample(
        network_data,
        source_slug=source_slug,
        count=count,
        seed=seed,
        era_bucket_count=era_bucket_count,
        density_low_max=density_low_max,
        density_basis=density_basis,
        proposal_type=proposal_type,
        exclude_ips=existing_ips,
    )

    new_rows = [
        {
            "ip": entry["ip"],
            "reviewer": reviewer,
            "reviewed_at": "",
            "sampling_strategy": "sampler",
            "sampling_snapshot": network_path.parents[1].name,
            "sampling_seed": str(seed),
            "era_bucket": entry["era_bucket"],
            "density_bucket": entry["density_bucket"],
            "density_basis": entry["density_basis"],
            "created": entry["created"],
            "status": entry["status"],
            "type": entry["type"],
            "layer": entry["layer"],
            "title": entry["title"],
            "extracted_target_count": str(entry["extracted_target_count"]),
            "note": "",
        }
        for entry in sampled
    ]

    rows_to_write = existing_rows + new_rows
    write_ips_csv(rows_to_write, output_path)

    return {
        "output_path": output_path,
        "existing_count": len(existing_rows),
        "added_count": len(new_rows),
        "requested_count": count,
        "total_count": len(rows_to_write),
        "proposal_type": proposal_type,
        "sampled_rows": new_rows,
        "strata_counts": Counter(
            f"{row['era_bucket']} / {row['density_bucket']}"
            for row in new_rows
        ),
    }
