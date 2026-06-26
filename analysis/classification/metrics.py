from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Tuple
from pipeline.source_context import SourceContext


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


def _node_triplet(
    node: Dict[str, Any], source_context: SourceContext
) -> Tuple[str, str, str]:
    layer = _apply_alias(
        _clean_base(node.get("layer"), "Unknown Layer"),
        source_context.classification_aliases("layer"),
    )
    status = _apply_alias(
        _clean_base(node.get("status"), "Unknown Status"),
        source_context.classification_aliases("status"),
    )
    kind = _apply_alias(
        _clean_base(node.get("type"), "Unknown Type"),
        source_context.classification_aliases("type"),
    )
    return layer, status, kind


def build_sankey_links(
    nodes: List[Dict[str, Any]],
    grouped_status: bool,
    source_context: SourceContext | None = None,
) -> List[Dict[str, Any]]:
    context = source_context or SourceContext.default()
    links = Counter()

    for node in nodes:
        layer, status, kind = _node_triplet(node, context)

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
        for (source, target), count in sorted(
            links.items(), key=lambda x: x[1], reverse=True
        )
    ]


def build_status_over_time(
    nodes: List[Dict[str, Any]],
    source_context: SourceContext | None = None,
) -> Dict[str, Dict[str, int]]:
    context = source_context or SourceContext.default()
    yearly = defaultdict(Counter)

    for node in nodes:
        year = _extract_year(node.get("created"))
        if year is None:
            continue
        status = _apply_alias(
            _clean_base(node.get("status"), "Unknown"),
            context.classification_aliases("status"),
        )
        yearly[year][status] += 1

    out: Dict[str, Dict[str, int]] = {}
    for year in sorted(yearly.keys()):
        out[str(year)] = dict(sorted(yearly[year].items(), key=lambda x: x[0]))
    return out


def build_type_over_time(
    nodes: List[Dict[str, Any]],
    source_context: SourceContext | None = None,
) -> Dict[str, Dict[str, int]]:
    context = source_context or SourceContext.default()
    yearly = defaultdict(Counter)

    for node in nodes:
        year = _extract_year(node.get("created"))
        if year is None:
            continue
        kind = _apply_alias(
            _clean_base(node.get("type"), "Unknown Type"),
            context.classification_aliases("type"),
        )
        yearly[year][kind] += 1

    out: Dict[str, Dict[str, int]] = {}
    for year in sorted(yearly.keys()):
        out[str(year)] = dict(sorted(yearly[year].items(), key=lambda x: x[0]))
    return out


def prepare_classification_payload(
    network_data: Dict[str, Any],
    source_context: SourceContext | None = None,
) -> Dict[str, Any]:
    context = source_context or SourceContext.default()
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
            "links": build_sankey_links(
                nodes, grouped_status=False, source_context=context
            ),
        },
        "sankey_grouped": {
            "links": build_sankey_links(
                nodes, grouped_status=True, source_context=context
            ),
        },
        "status_over_time": build_status_over_time(nodes, source_context=context),
    }
