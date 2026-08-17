from collections import Counter
from pathlib import Path
from typing import Any

from analysis.dependencies.constants import GROUND_TRUTH_CURATED
from analysis.interrelation_types import (
    INTERRELATION_TYPE_DEPENDS_ON,
    INTERRELATION_TYPE_REFERENCES,
    INTERRELATION_TYPE_SUPERSEDED_BY,
    INTERRELATION_TYPE_SUPERSEDES,
)

LATEX_TABCOLSEP_PT = 8
LATEX_ARRAYSTRETCH = 1.15
COMPONENT_RULE = r"\midrule"
DIMENSION_RULE = r"\cmidrule(lr){2-5}"
EDGE_TYPE_ORDER = [
    INTERRELATION_TYPE_DEPENDS_ON,
    INTERRELATION_TYPE_REFERENCES,
    INTERRELATION_TYPE_SUPERSEDES,
    INTERRELATION_TYPE_SUPERSEDED_BY,
]

DIMENSIONS = [
    {
        "label": "Status",
        "field": "status",
        "order": ["Draft", "Complete", "Deployed", "Closed"],
    },
    {
        "label": "Type",
        "field": "type",
        "order": ["Specification", "Informational", "Process"],
    },
]


def _latex_escape(value: object) -> str:
    return (
        str(value)
        .replace("\\", r"\textbackslash{}")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("$", r"\$")
        .replace("#", r"\#")
        .replace("_", r"\_")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("~", r"\textasciitilde{}")
        .replace("^", r"\textasciicircum{}")
    )


def _normalize_bucket(value: object) -> str:
    text = str(value or "").strip()
    return text or "unknown"


def _ordered_items(
    counter: Counter[str], preferred_order: list[str]
) -> list[tuple[str, int]]:
    ordered = [(key, counter[key]) for key in preferred_order if counter.get(key)]
    seen = {key for key, _count in ordered}
    ordered.extend(
        (key, count)
        for key, count in sorted(counter.items())
        if key not in seen and count
    )
    return ordered


def _share(count: int, total: int) -> str:
    if total <= 0:
        return "0.0\\%"
    return f"{(count / total) * 100:.1f}\\%"


def _reviewed_entries(network_data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        entry
        for entry in network_data.get("ground_truth_reviewed_ips", [])
        if str(entry.get("ip") or "").strip()
    ]


def _bip_to_bip_ground_truth_edges(
    network_data: dict[str, Any],
    reviewed_ips: set[str],
) -> list[dict[str, Any]]:
    reviewed_catalogs = {ip.partition(":")[0] for ip in reviewed_ips if ":" in ip}
    return [
        edge
        for edge in network_data.get("dependency_edges", [])
        if edge.get("extraction_method") == GROUND_TRUTH_CURATED
        and str(edge.get("source") or "").strip() in reviewed_ips
        and str(edge.get("target") or "").strip().partition(":")[0] in reviewed_catalogs
    ]


def _append_component(
    body_lines: list[str],
    component: str,
    sections: list[tuple[str, list[tuple[str, int, str]], bool]],
) -> None:
    row_count = sum(len(rows) for _dimension, rows, _monospace in sections)
    component_written = False
    for section_index, (dimension, rows, monospace_categories) in enumerate(sections):
        for row_index, (category, count, share) in enumerate(rows):
            cells = []
            if not component_written:
                cells.append(
                    rf"\multirow{{{row_count}}}{{*}}{{\textbf{{{_latex_escape(component)}}}}}"
                )
                component_written = True
            else:
                cells.append("")
            if row_index == 0:
                dimension_label = rf"\textbf{{{_latex_escape(dimension)}}}"
                cells.append(
                    rf"\multirow{{{len(rows)}}}{{*}}{{{dimension_label}}}"
                    if len(rows) > 1
                    else dimension_label
                )
            else:
                cells.append("")
            category_label = _latex_escape(category)
            if monospace_categories:
                category_label = rf"\texttt{{{category_label}}}"
            cells.extend([category_label, str(count), share])
            body_lines.append("        " + " & ".join(cells) + r" \\")
        if section_index < len(sections) - 1:
            body_lines.append(f"        {DIMENSION_RULE}%")


def export_ground_truth_dataset_latex_table(
    network_data: dict[str, Any],
    output_path: Path,
    *,
    tabcolsep_pt: int = LATEX_TABCOLSEP_PT,
) -> None:
    """Summarize the reviewed source-IP benchmark used for GT evaluation."""
    entries = _reviewed_entries(network_data)
    total = len(entries)
    reviewed_ips = {str(entry.get("ip") or "").strip() for entry in entries}
    edges = _bip_to_bip_ground_truth_edges(network_data, reviewed_ips)
    edge_count = len(edges)

    node_sections: list[tuple[str, list[tuple[str, int, str]], bool]] = [
        ("Total", [("Reviewed", total, "100.0\\%")], False)
    ]
    for dimension in DIMENSIONS:
        counter = Counter(
            _normalize_bucket(entry.get(dimension["field"])) for entry in entries
        )
        items = _ordered_items(counter, dimension["order"])
        node_sections.append(
            (
                dimension["label"],
                [(bucket, count, _share(count, total)) for bucket, count in items],
                True,
            )
        )

    edge_type_counts = Counter(
        _normalize_bucket(edge.get("relation_type")) for edge in edges
    )
    edge_type_rows = [
        (edge_type, count, _share(count, edge_count))
        for edge_type, count in _ordered_items(edge_type_counts, EDGE_TYPE_ORDER)
    ]
    edge_sections = [
        ("Total", [("Reviewed", edge_count, "100.0\\%")], False),
        ("Type", edge_type_rows, True),
    ]

    body_lines: list[str] = []
    _append_component(body_lines, "Nodes", node_sections)
    body_lines.append(f"        {COMPONENT_RULE}%")
    _append_component(body_lines, "Edges", edge_sections)

    latex_table = "\n".join(
        [
            "{%",
            r"    \setlength{\abovetopsep}{0pt}%",
            r"    \setlength{\belowbottomsep}{0pt}%",
            r"    \setlength{\aboverulesep}{0pt}%",
            r"    \setlength{\belowrulesep}{0pt}%",
            rf"    \setlength{{\tabcolsep}}{{{tabcolsep_pt}pt}}%",
            rf"    \renewcommand{{\arraystretch}}{{{LATEX_ARRAYSTRETCH}}}%",
            r"    \begin{tabular}{l l|l r r}",
            r"        \toprule",
            r"        \textbf{Component} & \textbf{Dimension} & \textbf{Category} & \textbf{Count} & \textbf{Share} \\",
            r"        \midrule%",
            *body_lines,
            r"        \bottomrule",
            r"    \end{tabular}%",
            "}",
            "",
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(latex_table, encoding="utf-8")
