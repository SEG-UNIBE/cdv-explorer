from collections import Counter
from pathlib import Path
from typing import Any

from analysis.dependencies.constants import GROUND_TRUTH_CURATED

LATEX_TABCOLSEP_PT = 8
LATEX_ARRAYSTRETCH = 1.15
SECTION_RULE = r"\midrule"

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


def _bip_to_bip_ground_truth_edge_count(
    network_data: dict[str, Any],
    reviewed_ips: set[str],
) -> int:
    reviewed_catalogs = {ip.partition(":")[0] for ip in reviewed_ips if ":" in ip}
    return sum(
        1
        for edge in network_data.get("dependency_edges", [])
        if edge.get("extraction_method") == GROUND_TRUTH_CURATED
        and str(edge.get("source") or "").strip() in reviewed_ips
        and str(edge.get("target") or "").strip().partition(":")[0] in reviewed_catalogs
    )


def _append_section(
    body_lines: list[str],
    label: str,
    rows: list[tuple[str, int, str]],
) -> None:
    for row_index, (category, count, share) in enumerate(rows):
        cells = []
        if row_index == 0:
            cells.append(
                rf"\multirow{{{len(rows)}}}{{*}}{{\textbf{{{_latex_escape(label)}}}}}"
            )
        else:
            cells.append("")
        cells.extend([_latex_escape(category), str(count), share])
        body_lines.append("        " + " & ".join(cells) + r" \\")


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
    edge_count = _bip_to_bip_ground_truth_edge_count(network_data, reviewed_ips)

    body_lines = []
    _append_section(
        body_lines,
        "Benchmark",
        [
            ("Reviewed BIPs", total, "100.0\\%"),
            ("BIP-to-BIP GT edges", edge_count, "-"),
        ],
    )
    body_lines.append(f"        {SECTION_RULE}%")

    for dimension_index, dimension in enumerate(DIMENSIONS):
        counter = Counter(
            _normalize_bucket(entry.get(dimension["field"])) for entry in entries
        )
        items = _ordered_items(counter, dimension["order"])
        for row_index, (bucket, count) in enumerate(items):
            cells = []
            if row_index == 0:
                cells.append(
                    rf"\multirow{{{len(items)}}}{{*}}{{\textbf{{{_latex_escape(dimension['label'])}}}}}"
                )
            else:
                cells.append("")
            cells.extend([_latex_escape(bucket), str(count), _share(count, total)])
            body_lines.append("        " + " & ".join(cells) + r" \\")
        if dimension_index < len(DIMENSIONS) - 1:
            body_lines.append(f"        {SECTION_RULE}%")

    latex_table = "\n".join(
        [
            "{%",
            r"    \setlength{\abovetopsep}{0pt}%",
            r"    \setlength{\belowbottomsep}{0pt}%",
            r"    \setlength{\aboverulesep}{0pt}%",
            r"    \setlength{\belowrulesep}{0pt}%",
            rf"    \setlength{{\tabcolsep}}{{{tabcolsep_pt}pt}}%",
            rf"    \renewcommand{{\arraystretch}}{{{LATEX_ARRAYSTRETCH}}}%",
            r"    \begin{tabular}{l|l r r}",
            r"        \toprule",
            r"        \textbf{Dimension} & \textbf{Category} & \textbf{Count} & \textbf{Share} \\",
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
