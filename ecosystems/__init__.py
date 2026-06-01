import yaml
from pathlib import Path

_DIR = Path(__file__).parent


def _load_registry() -> dict:
    registry: dict = {}
    for yml_file in sorted(_DIR.glob("*.yml")):
        data = yaml.safe_load(yml_file.read_text(encoding="utf-8"))
        slug = data.get("slug") or yml_file.stem
        registry[slug] = data
    return registry


ECOSYSTEM_REGISTRY = _load_registry()
