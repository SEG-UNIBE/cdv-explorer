import json
from functools import lru_cache
from pathlib import Path
from typing import Any

EXTERNAL_LINKS_PATH = (
    Path(__file__).resolve().parents[1] / "react" / "src" / "externalLinks.json"
)


@lru_cache(maxsize=1)
def load_external_links() -> dict[str, Any]:
    with EXTERNAL_LINKS_PATH.open(encoding="utf-8") as handle:
        payload: dict[str, Any] = json.load(handle)
        return payload


def get_bips_dev_base_url() -> str:
    return str(load_external_links().get("bipsDevBaseUrl", "")).rstrip("/")
