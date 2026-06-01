import json
from functools import lru_cache
from pathlib import Path


EXTERNAL_LINKS_PATH = Path(__file__).resolve().parents[1] / "react" / "src" / "externalLinks.json"


@lru_cache(maxsize=1)
def load_external_links():
    with EXTERNAL_LINKS_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def get_bips_dev_base_url():
    return str(load_external_links().get("bipsDevBaseUrl", "")).rstrip("/")
