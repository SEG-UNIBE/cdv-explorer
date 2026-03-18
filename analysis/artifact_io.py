import json
from pathlib import Path
from typing import Any, Dict

from ecosystem_config import ACTIVE_ECOSYSTEM


def resolve_network_data_artifact(snapshot: str | None = None) -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    artifact_root = repo_root / ACTIVE_ECOSYSTEM["analysis"]

    candidates = []
    if snapshot:
        candidates.append(artifact_root / snapshot / "dependencies" / "network_data.json")

    candidates.append(artifact_root / "latest" / "dependencies" / "network_data.json")

    for candidate in candidates:
        if candidate.exists():
            return candidate

    tried = "\n".join(f"- {c}" for c in candidates)
    raise FileNotFoundError(f"Could not find a network_data artifact. Tried:\n{tried}")


def load_network_data(snapshot: str | None = None) -> Dict[str, Any]:
    artifact_path = resolve_network_data_artifact(snapshot=snapshot)

    if artifact_path.suffix != ".json":
        raise ValueError(f"Unsupported artifact extension: {artifact_path.suffix}")

    with artifact_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    return data
