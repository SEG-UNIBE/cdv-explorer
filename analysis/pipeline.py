import json
from pathlib import Path
from typing import Any, Dict, List

from analysis.authorship import extract_authorship_metrics
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


def prepare_ecosystem_artifacts(
    proposal_json_dir: Path,
    artifact_root: Path,
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
    network_stem = artifact_root / "dependencies" / f"network_data_{stichtag}"
    save_network_data_artifacts(network_data, network_stem)

    authorship_metrics = extract_authorship_metrics(network_data.get("nodes", []))
    authorship_path = artifact_root / "authorship" / f"authorship_{stichtag}.json"
    _save_json(authorship_metrics, authorship_path)

    conformity_metrics = extract_conformity_metrics(proposal_data, id_field=id_field)
    conformity_path = artifact_root / "conformity" / f"conformity_{stichtag}.json"
    _save_json(conformity_metrics, conformity_path)

    return {
        "network_json": network_stem.with_suffix(".json"),
        "network_pkl": network_stem.with_suffix(".pkl"),
        "authorship_json": authorship_path,
        "conformity_json": conformity_path,
    }
