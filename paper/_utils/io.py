from datetime import datetime
from pathlib import Path


def get_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_output_dir(path_value: str | None, default_relative_path: Path) -> Path:
    if path_value:
        output_path = Path(path_value)
        if output_path.is_absolute():
            return output_path
        return get_repo_root() / output_path

    return get_repo_root() / default_relative_path


def snapshot_prefix(snapshot_label: str) -> str:
    try:
        return datetime.strptime(snapshot_label, "%Y-%m-%d").strftime("%y%m%d")
    except ValueError:
        return snapshot_label.replace("-", "")
