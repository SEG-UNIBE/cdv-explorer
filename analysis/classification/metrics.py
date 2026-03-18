from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Tuple
from ecosystem_config import ACTIVE_ECOSYSTEM

CLASSIFICATION_CONFIG = ACTIVE_ECOSYSTEM.get("classification", {})
LAYER_ALIASES = CLASSIFICATION_CONFIG.get("layer_aliases", {})
STATUS_ALIASES = CLASSIFICATION_CONFIG.get("status_aliases", {})
TYPE_ALIASES = CLASSIFICATION_CONFIG.get("type_aliases", {})


def _clean_base(value: Any, fallback: str) -> str:
    text = str(value).strip() if value is not None else ""
    return text or fallback


def _apply_alias(value: str, aliases: Dict[str, str]) -> str:
    return aliases.get(value, value)


def _base_status(status_text: str) -> str:
    return status_text.split("(")[0].strip()


def _extract_year(date_text: Any) -> int | None:
    if not date_text:
        return None
    try:
        return datetime.strptime(str(date_text), "%Y-%m-%d").year
    except ValueError:
        return None


def _node_triplet(node: Dict[str, Any]) -> Tuple[str, str, str]:
    layer = _apply_alias(_clean_base(node.get("layer"), "Unknown Layer"), LAYER_ALIASES)
    status = _apply_alias(_clean_base(node.get("status"), "Unknown Status"), STATUS_ALIASES)
    kind = _apply_alias(_clean_base(node.get("type"), "Unknown Type"), TYPE_ALIASES)
    return layer, status, kind


def build_sankey_links(nodes: List[Dict[str, Any]], grouped_status: bool) -> List[Dict[str, Any]]:
    links = Counter()

    for node in nodes:
        layer, status, kind = _node_triplet(node)

        if grouped_status:
            status = _base_status(status)
            if "Unknown" in layer:
                layer = "Other"
            if "Unknown" in status:
                status = "Unknown Status"
            if "Unknown" in kind:
                kind = "Unknown Type"
        else:
            if "Unknown" in layer or "Unknown" in status or "Unknown" in kind:
                continue

        links[(layer, status)] += 1
        links[(status, kind)] += 1

    return [
        {"source": source, "target": target, "count": count}
        for (source, target), count in sorted(links.items(), key=lambda x: x[1], reverse=True)
    ]


def build_status_over_time(nodes: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    yearly = defaultdict(Counter)

    for node in nodes:
        year = _extract_year(node.get("created"))
        if year is None:
            continue
        status = _apply_alias(_clean_base(node.get("status"), "Unknown"), STATUS_ALIASES)
        yearly[year][status] += 1

    out: Dict[str, Dict[str, int]] = {}
    for year in sorted(yearly.keys()):
        out[str(year)] = dict(sorted(yearly[year].items(), key=lambda x: x[0]))
    return out


def prepare_classification_payload(network_data: Dict[str, Any]) -> Dict[str, Any]:
    nodes = network_data.get("nodes", [])

    return {
        "meta": {
            "node_count": len(nodes),
            "generated_metrics": [
                "sankey_full",
                "sankey_grouped",
                "status_over_time",
            ],
        },
        "sankey_full": {
            "links": build_sankey_links(nodes, grouped_status=False),
        },
        "sankey_grouped": {
            "links": build_sankey_links(nodes, grouped_status=True),
        },
        "status_over_time": build_status_over_time(nodes),
    }
