import json
from pathlib import Path
from typing import Any

from pipeline.source_context import SourceContext


def get_analysis_artifact_root() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    return repo_root / SourceContext.default().config["analysis"]


def get_postprocess_artifact_root() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    return repo_root / SourceContext.default().config["postprocess"]


def resolve_latest_snapshot_label(artifact_root: Path | None = None) -> str | None:
    root = artifact_root if artifact_root is not None else get_analysis_artifact_root()
    if not root.exists():
        return None

    dated_snapshots = sorted(
        path.name
        for path in root.iterdir()
        if path.is_dir() and path.name != "latest"
    )
    return dated_snapshots[-1] if dated_snapshots else None


def _resolve_snapshot_artifact(
    artifact_root: Path, snapshot: str | None, *relative_parts: str
) -> Path:
    candidates = []
    if snapshot:
        candidates.append(artifact_root / snapshot / Path(*relative_parts))

    candidates.append(artifact_root / "latest" / Path(*relative_parts))

    latest_snapshot = resolve_latest_snapshot_label(artifact_root)
    if latest_snapshot:
        candidates.append(artifact_root / latest_snapshot / Path(*relative_parts))

    for candidate in candidates:
        if candidate.exists():
            return candidate

    tried = "\n".join(f"- {c}" for c in candidates)
    artifact_name = "/".join(relative_parts)
    raise FileNotFoundError(f"Could not find artifact {artifact_name}. Tried:\n{tried}")


def _resolve_payload_artifact(snapshot: str | None, *relative_parts: str) -> Path:
    return _resolve_snapshot_artifact(
        get_postprocess_artifact_root(), snapshot, *relative_parts
    )


def _resolve_analysis_artifact(snapshot: str | None, *relative_parts: str) -> Path:
    return _resolve_snapshot_artifact(
        get_analysis_artifact_root(), snapshot, *relative_parts
    )


def resolve_network_data_artifact(snapshot: str | None = None) -> Path:
    return _resolve_payload_artifact(snapshot, "dependencies", "network_data.json")


def resolve_dependency_metrics_artifact(snapshot: str | None = None) -> Path:
    return _resolve_payload_artifact(
        snapshot, "dependencies", "dependency_metrics.json"
    )


def resolve_authorship_metrics_artifact(snapshot: str | None = None) -> Path:
    return _resolve_analysis_artifact(
        snapshot, "authorship", "authorship_metrics.json"
    )


def resolve_authorship_payload_artifact(snapshot: str | None = None) -> Path:
    return _resolve_payload_artifact(snapshot, "authorship", "authorship_payload.json")


def resolve_classification_payload_artifact(snapshot: str | None = None) -> Path:
    return _resolve_payload_artifact(
        snapshot, "classification", "classification_payload.json"
    )


def resolve_evolution_payload_artifact(snapshot: str | None = None) -> Path:
    return _resolve_payload_artifact(snapshot, "evolution", "evolution_payload.json")


def _load_json_artifact(artifact_path: Path) -> dict[str, Any]:
    if artifact_path.suffix != ".json":
        raise ValueError(f"Unsupported artifact extension: {artifact_path.suffix}")

    with artifact_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    return data


def load_network_data(snapshot: str | None = None) -> dict[str, Any]:
    artifact_path = resolve_network_data_artifact(snapshot=snapshot)
    return _load_json_artifact(artifact_path)


def load_dependency_metrics(snapshot: str | None = None) -> dict[str, Any]:
    artifact_path = resolve_dependency_metrics_artifact(snapshot=snapshot)
    return _load_json_artifact(artifact_path)


def load_authorship_metrics(snapshot: str | None = None) -> dict[str, Any]:
    artifact_path = resolve_authorship_metrics_artifact(snapshot=snapshot)
    return _load_json_artifact(artifact_path)


def load_authorship_payload(snapshot: str | None = None) -> dict[str, Any]:
    artifact_path = resolve_authorship_payload_artifact(snapshot=snapshot)
    return _load_json_artifact(artifact_path)


def load_classification_payload(snapshot: str | None = None) -> dict[str, Any]:
    artifact_path = resolve_classification_payload_artifact(snapshot=snapshot)
    return _load_json_artifact(artifact_path)


def load_evolution_payload(snapshot: str | None = None) -> dict[str, Any]:
    artifact_path = resolve_evolution_payload_artifact(snapshot=snapshot)
    return _load_json_artifact(artifact_path)
