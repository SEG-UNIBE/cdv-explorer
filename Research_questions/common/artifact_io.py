import json
import pickle
from pathlib import Path
from typing import Any, Dict

from ecosystem_config import ACTIVE_ECOSYSTEM


def resolve_network_data_artifact(stichtag: str | None = None, prefer_json: bool = True) -> Path:
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parents[1]
    ecosystem_artifacts_dir = repo_root / ACTIVE_ECOSYSTEM["artifact_directory"] / "dependencies"
    legacy_artifacts_dir = repo_root / "Research_questions" / "artifacts" / "network_data"

    ext_primary = ".json" if prefer_json else ".pkl"
    ext_secondary = ".pkl" if prefer_json else ".json"

    candidates = []
    if stichtag:
        candidates.extend(
            [
                ecosystem_artifacts_dir / f"network_data_{stichtag}{ext_primary}",
                ecosystem_artifacts_dir / f"network_data_{stichtag}{ext_secondary}",
                legacy_artifacts_dir / f"network_data_{stichtag}{ext_primary}",
                legacy_artifacts_dir / f"network_data_{stichtag}{ext_secondary}",
            ]
        )

    candidates.extend(
        [
            ecosystem_artifacts_dir / f"network_data_latest{ext_primary}",
            ecosystem_artifacts_dir / f"network_data_latest{ext_secondary}",
            legacy_artifacts_dir / f"network_data_latest{ext_primary}",
            legacy_artifacts_dir / f"network_data_latest{ext_secondary}",
            repo_root / "Research_questions" / f"network_data{ext_secondary}",
            repo_root / "Research_questions" / f"network_data{ext_primary}",
            repo_root / f"network_data{ext_secondary}",
            repo_root / f"network_data{ext_primary}",
            Path.cwd() / f"network_data{ext_secondary}",
            Path.cwd() / f"network_data{ext_primary}",
        ]
    )

    for candidate in candidates:
        if candidate.exists():
            return candidate

    tried = "\n".join(f"- {c}" for c in candidates)
    raise FileNotFoundError(f"Could not find a network_data artifact. Tried:\n{tried}")


def load_network_data(stichtag: str | None = None, prefer_json: bool = True) -> Dict[str, Any]:
    artifact_path = resolve_network_data_artifact(stichtag=stichtag, prefer_json=prefer_json)

    if artifact_path.suffix == ".json":
        with artifact_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    elif artifact_path.suffix == ".pkl":
        with artifact_path.open("rb") as handle:
            data = pickle.load(handle)
    else:
        raise ValueError(f"Unsupported artifact extension: {artifact_path.suffix}")

    print(f"Loaded network data from: {artifact_path}")
    return data
