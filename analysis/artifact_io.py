import json
from pathlib import Path
from typing import Any, Dict

from pipeline.ecosystem_config import ACTIVE_ECOSYSTEM


def get_analysis_artifact_root() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    return repo_root / ACTIVE_ECOSYSTEM["analysis"]


def resolve_latest_snapshot_label() -> str | None:
    artifact_root = get_analysis_artifact_root()
    if not artifact_root.exists():
        return None

    dated_snapshots = sorted(
        path.name
        for path in artifact_root.iterdir()
        if path.is_dir() and path.name != "latest"
    )
    return dated_snapshots[-1] if dated_snapshots else None


def _resolve_snapshot_artifact(snapshot: str | None, *relative_parts: str) -> Path:
    artifact_root = get_analysis_artifact_root()

    candidates = []
    if snapshot:
        candidates.append(artifact_root / snapshot / Path(*relative_parts))

    candidates.append(artifact_root / "latest" / Path(*relative_parts))

    latest_snapshot = resolve_latest_snapshot_label()
    if latest_snapshot:
        candidates.append(artifact_root / latest_snapshot / Path(*relative_parts))

    for candidate in candidates:
        if candidate.exists():
            return candidate

    tried = "\n".join(f"- {c}" for c in candidates)
    artifact_name = "/".join(relative_parts)
    raise FileNotFoundError(f"Could not find artifact {artifact_name}. Tried:\n{tried}")


def resolve_network_data_artifact(snapshot: str | None = None) -> Path:
    return _resolve_snapshot_artifact(snapshot, "dependencies", "network_data.json")


def resolve_dependency_metrics_artifact(snapshot: str | None = None) -> Path:
    return _resolve_snapshot_artifact(snapshot, "dependencies", "dependency_metrics.json")


def resolve_authorship_metrics_artifact(snapshot: str | None = None) -> Path:
    return _resolve_snapshot_artifact(snapshot, "authorship", "authorship_metrics.json")


def resolve_authorship_payload_artifact(snapshot: str | None = None) -> Path:
    return _resolve_snapshot_artifact(snapshot, "authorship", "authorship_payload.json")


def resolve_classification_payload_artifact(snapshot: str | None = None) -> Path:
    return _resolve_snapshot_artifact(snapshot, "classification", "classification_payload.json")


def resolve_evolution_payload_artifact(snapshot: str | None = None) -> Path:
    return _resolve_snapshot_artifact(snapshot, "evolution", "evolution_payload.json")


def _load_json_artifact(artifact_path: Path) -> Dict[str, Any]:
    if artifact_path.suffix != ".json":
        raise ValueError(f"Unsupported artifact extension: {artifact_path.suffix}")

    with artifact_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    return data


def load_network_data(snapshot: str | None = None) -> Dict[str, Any]:
    artifact_path = resolve_network_data_artifact(snapshot=snapshot)
    return _load_json_artifact(artifact_path)


def load_dependency_metrics(snapshot: str | None = None) -> Dict[str, Any]:
    artifact_path = resolve_dependency_metrics_artifact(snapshot=snapshot)
    return _load_json_artifact(artifact_path)


def load_authorship_metrics(snapshot: str | None = None) -> Dict[str, Any]:
    artifact_path = resolve_authorship_metrics_artifact(snapshot=snapshot)
    return _load_json_artifact(artifact_path)


def load_authorship_payload(snapshot: str | None = None) -> Dict[str, Any]:
    artifact_path = resolve_authorship_payload_artifact(snapshot=snapshot)
    return _load_json_artifact(artifact_path)


def load_classification_payload(snapshot: str | None = None) -> Dict[str, Any]:
    artifact_path = resolve_classification_payload_artifact(snapshot=snapshot)
    return _load_json_artifact(artifact_path)


def load_evolution_payload(snapshot: str | None = None) -> Dict[str, Any]:
    artifact_path = resolve_evolution_payload_artifact(snapshot=snapshot)
    return _load_json_artifact(artifact_path)
