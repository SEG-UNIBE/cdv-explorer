from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator, MultipleLocator
from matplotlib.transforms import ScaledTranslation

from paper.RQ3._plotting import (
    BAR_EDGE_COLOR,
    bar_style,
    despine,
    match_axis_label_fontsize,
)


REACT_CLASSIFICATION_PALETTE = [
    "#4e79a7",
    "#f28e2c",
    "#e15759",
    "#76b7b2",
    "#59a14f",
    "#edc949",
    "#af7aa1",
    "#ff9da7",
    "#9c755f",
    "#bab0ab",
    "#66c2a5",
    "#fc8d62",
    "#8da0cb",
    "#e78ac3",
    "#a6d854",
    "#ffd92f",
    "#e5c494",
    "#b3b3b3",
    "#8dd3c7",
    "#ffffb3",
    "#bebada",
    "#fb8072",
    "#80b1d3",
    "#fdb462",
    "#b3de69",
    "#fccde5",
    "#d9d9d9",
    "#bc80bd",
    "#ccebc5",
    "#ffed6f",
]

HATCH_BIP3 = "/////"
HATCH_LINEWIDTH = 0.2
BIP3_ALLOWED_STATUSES = {"Draft", "Complete", "Deployed", "Closed"}
BIP3_DRAFT_START_PERIOD = "2026-Q1"
ACTIVATION_GAP = 0.45
ACTIVATION_YEAR_LABEL_NUDGE_POINTS = 6
BAR_WIDTH = 0.82
EVOLUTION_BAR_EDGE_WIDTH = 0.5
FIXED_STATUS_COLORS = {
    "Draft": "#4e79a7",
    "Active": "#f28e2c",
    "Proposed": "#59a14f",
    "Deferred": "#76b7b2",
    "Rejected": "#e15759",
    "Withdrawn": "#edc949",
    "Final": "#af7aa1",
    "Replaced": "#ff9da7",
    "Obsolete": "#9c755f",
    "Accepted": "#bab0ab",
    "Complete": "#66c2a5",
    "Deployed": "#fc8d62",
    "Closed": "#868e96",
}


def _evolution_bar_style(color: str) -> dict[str, object]:
    style = bar_style(color)
    style["linewidth"] = EVOLUTION_BAR_EDGE_WIDTH
    return style


def _react_color_map(categories: list[str]) -> dict[str, str]:
    return {
        category: FIXED_STATUS_COLORS.get(
            category,
            REACT_CLASSIFICATION_PALETTE[index % len(REACT_CLASSIFICATION_PALETTE)],
        )
        for index, category in enumerate(categories)
    }


def _format_period_display_label(period_key: str, period_label: str) -> str:
    if period_key.endswith("-pre-bip3"):
        return f"{period_label}a"
    if period_key.endswith("-post-bip3"):
        return f"{period_label}b"
    return period_label


def _format_milestone_label(label: str) -> str:
    if label.strip() == "BIP3 Activation":
        return "BIP3 activation"
    return label


def _normalize_evolution_series(
    status_evolution: dict[str, Any],
) -> tuple[list[str], list[str], dict[str, list[int]]]:
    rows = [
        {
            "period": str(row.get("period") or row.get("year") or "").strip(),
            "values": row.get("values") or {},
        }
        for row in (status_evolution.get("rows") or [])
        if str(row.get("period") or row.get("year") or "").strip()
    ]
    if not rows:
        raise ValueError("Status evolution plot requires non-empty quarterly rows.")

    rows.sort(key=lambda row: row["period"])

    preferred_categories = [
        str(category).strip()
        for category in (status_evolution.get("categories") or [])
        if str(category).strip()
    ]
    observed_categories = list(
        dict.fromkeys(
            status
            for row in rows
            for status, value in row["values"].items()
            if int(value) > 0
        )
    )
    ordered_categories = [
        category
        for category in preferred_categories
        if category in observed_categories
    ]
    ordered_categories.extend(
        category
        for category in observed_categories
        if category not in ordered_categories
    )
    if not ordered_categories:
        raise ValueError("Status evolution plot requires at least one positive status count.")

    periods = [row["period"] for row in rows]
    series = {
        category: [
            int(row["values"].get(category, 0))
            for row in rows
        ]
        for category in ordered_categories
    }
    return periods, ordered_categories, series


def _normalize_standard_rows(
    status_evolution_by_standard: dict[str, Any] | None,
) -> dict[str, dict[str, dict[str, int]]]:
    normalized: dict[str, dict[str, dict[str, int]]] = {}
    for standard in ("bip2", "bip3"):
        standard_data = (status_evolution_by_standard or {}).get(standard) or {}
        rows = standard_data.get("rows") or []
        normalized[standard] = {
            str(row.get("period") or row.get("year") or "").strip(): {
                str(status).strip(): int(value)
                for status, value in (row.get("values") or {}).items()
                if str(status).strip()
            }
            for row in rows
            if str(row.get("period") or row.get("year") or "").strip()
        }
    return normalized


def _normalize_segmented_rows(
    status_evolution_segmented: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[str], dict[str, list[int]], dict[str, list[str]]]:
    segmented = status_evolution_segmented or {}
    raw_segment_definitions = segmented.get("segmentDefinitions") or []
    raw_rows = segmented.get("rows") or []
    if not raw_segment_definitions or not raw_rows:
        raise ValueError("Segmented evolution data is unavailable.")

    rows = [
        {
            "period_key": str(row.get("period_key") or row.get("period") or row.get("year") or "").strip(),
            "period": str(row.get("period") or row.get("year") or "").strip(),
            "period_end": str(row.get("period_end") or "").strip(),
            "period_kind": str(row.get("period_kind") or "quarter").strip(),
            "milestone_label": str(row.get("milestone_label") or "").strip(),
            "values": {
                str(key).strip(): int(value)
                for key, value in (row.get("values") or {}).items()
                if str(key).strip()
            },
            "index": index,
        }
        for index, row in enumerate(raw_rows)
        if str(row.get("period_key") or row.get("period") or row.get("year") or "").strip()
    ]
    if not rows:
        raise ValueError("Segmented evolution data is missing rows.")

    rows.sort(key=lambda row: (row["period_end"], row["index"]))

    segment_definitions = [
        {
            "key": str(segment.get("key") or "").strip(),
            "status": str(segment.get("status") or "").strip(),
            "standard": str(segment.get("standard") or "").strip(),
        }
        for segment in raw_segment_definitions
        if str(segment.get("key") or "").strip()
    ]
    if not segment_definitions:
        raise ValueError("Segmented evolution data is missing segment definitions.")

    totals_by_segment = {
        segment["key"]: sum(int(row["values"].get(segment["key"], 0)) for row in rows)
        for segment in segment_definitions
    }
    visible_segment_definitions = [
        segment
        for segment in segment_definitions
        if totals_by_segment.get(segment["key"], 0) > 0
    ]
    if not visible_segment_definitions:
        raise ValueError("Segmented evolution plot requires at least one positive segment.")

    ordered_statuses = list(dict.fromkeys(segment["status"] for segment in visible_segment_definitions))
    segment_series = {
        segment["key"]: [int(row["values"].get(segment["key"], 0)) for row in rows]
        for segment in visible_segment_definitions
    }
    legend_statuses = {
        "bip2": list(dict.fromkeys(
            segment["status"] for segment in visible_segment_definitions if segment["standard"] == "bip2"
        )),
        "bip3": list(dict.fromkeys(
            segment["status"] for segment in visible_segment_definitions if segment["standard"] == "bip3"
        )),
    }

    for row in rows:
        row["display_label"] = _format_period_display_label(row["period_key"], row["period"])

    return rows, visible_segment_definitions, ordered_statuses, segment_series, legend_statuses


def _can_render_as_bip3(status: str, period: str) -> bool:
    if status not in BIP3_ALLOWED_STATUSES:
        return False
    if status == "Draft" and period < BIP3_DRAFT_START_PERIOD:
        return False
    return True


def _build_segment_definitions(
    periods: list[str],
    ordered_statuses: list[str],
    series: dict[str, list[int]],
    status_evolution_by_standard: dict[str, Any] | None,
) -> tuple[list[tuple[str, str]], dict[str, list[int]], dict[str, list[str]]]:
    standard_rows = _normalize_standard_rows(status_evolution_by_standard)
    segment_order: list[tuple[str, str]] = []
    segment_series: dict[str, list[int]] = {}
    legend_statuses = {"bip2": [], "bip3": []}

    for status in ordered_statuses:
        total_counts = series[status]
        bip3_counts = []
        bip2_counts = []

        for index, period in enumerate(periods):
            total_count = int(total_counts[index])
            raw_bip3_count = int(standard_rows["bip3"].get(period, {}).get(status, 0))
            bip3_count = raw_bip3_count if _can_render_as_bip3(status, period) else 0
            bip3_count = max(0, min(total_count, bip3_count))
            bip2_count = total_count - bip3_count
            bip3_counts.append(bip3_count)
            bip2_counts.append(bip2_count)

        if any(count > 0 for count in bip2_counts):
            segment_order.append((status, "bip2"))
            segment_series[f"{status}|||bip2"] = bip2_counts
            legend_statuses["bip2"].append(status)

        if any(count > 0 for count in bip3_counts):
            segment_order.append((status, "bip3"))
            segment_series[f"{status}|||bip3"] = bip3_counts
            legend_statuses["bip3"].append(status)

    return segment_order, segment_series, legend_statuses


def _build_period_positions(rows: list[dict[str, Any]]) -> np.ndarray:
    positions: list[float] = []
    current_position = 0.0
    for index, row in enumerate(rows):
        positions.append(current_position)
        current_position += 1.0
        if row.get("period_kind") == "milestone" and index < len(rows) - 1:
            current_position += ACTIVATION_GAP
    return np.array(positions, dtype=float)


def _select_tick_positions(rows: list[dict[str, Any]], x_positions: np.ndarray) -> tuple[np.ndarray, list[str]]:
    positions_by_label: dict[str, list[float]] = {}
    label_order: list[str] = []
    activation_years = {
        str(row.get("period") or "").strip().split("-", 1)[0]
        for row in rows
        if str(row.get("period_key") or "").strip().endswith("-post-bip3")
        and str(row.get("period") or "").strip()
        and "-" in str(row.get("period") or "").strip()
    }

    for index, row in enumerate(rows):
        period_label = str(row.get("period") or "").strip()
        if not period_label or "-" not in period_label:
            continue
        year = period_label.split("-", 1)[0]
        period_key = str(row.get("period_key") or "").strip()

        if year in activation_years:
            tick_label = year[-2:] if period_key.endswith("-pre-bip3") else f"{year[-2:]}'"
        else:
            tick_label = year

        if tick_label not in positions_by_label:
            label_order.append(tick_label)
        positions_by_label.setdefault(tick_label, []).append(float(x_positions[index]))

    if positions_by_label:
        tick_labels = label_order
        tick_positions = [
            sum(positions_by_label[label]) / len(positions_by_label[label])
            for label in tick_labels
        ]
        return np.array(tick_positions, dtype=float), tick_labels

    fallback_positions = [float(value) for value in x_positions]
    fallback_labels = [str(row.get("period") or "") for row in rows]
    return np.array(fallback_positions, dtype=float), fallback_labels


def plot_evolution_status(
    status_evolution: dict[str, Any],
    output_path: Path,
    snapshot_label: str,
    *,
    status_evolution_by_standard: dict[str, Any] | None = None,
    status_evolution_segmented: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
    category_title: str = "Status Evolution",
    y_axis_title: str = "Number of BIPs",
) -> None:
    del meta

    try:
        rows, visible_segment_definitions, ordered_statuses, segment_series, legend_statuses = _normalize_segmented_rows(
            status_evolution_segmented,
        )
        plot_segments = [
            {
                "key": segment["key"],
                "status": segment["status"],
                "standard": segment["standard"] or "bip2",
            }
            for segment in visible_segment_definitions
        ]
    except ValueError:
        periods, ordered_statuses, series = _normalize_evolution_series(status_evolution)
        segment_order, segment_series, legend_statuses = _build_segment_definitions(
            periods,
            ordered_statuses,
            series,
            status_evolution_by_standard,
        )
        if not segment_order:
            segment_order = [(status, "bip2") for status in ordered_statuses]
            segment_series = {
                f"{status}|||bip2": counts
                for status, counts in series.items()
            }
            legend_statuses = {
                "bip2": list(ordered_statuses),
                "bip3": [],
            }

        rows = [
            {
                "period_key": period,
                "period": period,
                "display_label": period,
                "period_kind": "quarter",
                "milestone_label": "",
            }
            for period in periods
        ]
        plot_segments = [
            {
                "key": f"{status}|||{standard}",
                "status": status,
                "standard": standard,
            }
            for status, standard in segment_order
        ]

    x_positions = _build_period_positions(rows)
    color_map = _react_color_map(ordered_statuses)

    bip2_handles = [
        Patch(
            facecolor=_evolution_bar_style(color_map[status])["color"],
            edgecolor=BAR_EDGE_COLOR,
            linewidth=EVOLUTION_BAR_EDGE_WIDTH,
            label=status,
        )
        for status in reversed(legend_statuses["bip2"])
    ]
    bip3_handles = [
        Patch(
            facecolor=_evolution_bar_style(color_map[status])["color"],
            edgecolor=BAR_EDGE_COLOR,
            linewidth=EVOLUTION_BAR_EDGE_WIDTH,
            hatch=HATCH_BIP3,
            label=status,
        )
        for status in reversed(legend_statuses["bip3"])
    ]

    bar_bottom = np.zeros(len(rows), dtype=int)

    matplotlib.rcParams["hatch.linewidth"] = HATCH_LINEWIDTH
    figure, axis = plt.subplots(figsize=(10, 5))

    for segment in plot_segments:
        counts = np.array(segment_series[segment["key"]], dtype=int)
        positive_mask = counts > 0
        if np.any(positive_mask):
            axis.bar(
                x_positions[positive_mask],
                counts[positive_mask],
                bottom=bar_bottom[positive_mask],
                width=BAR_WIDTH,
                zorder=3,
                hatch=HATCH_BIP3 if segment["standard"] == "bip3" else None,
                **_evolution_bar_style(color_map[segment["status"]]),
            )
        bar_bottom = bar_bottom + counts

    major_tick_positions, major_tick_labels = _select_tick_positions(rows, x_positions)
    axis.set_xticks(major_tick_positions)
    axis.set_xticklabels(major_tick_labels, rotation=0, ha="center")
    for tick_label in axis.get_xticklabels():
        text = tick_label.get_text().strip()
        if text == "26 ":
            tick_label.set_transform(
                tick_label.get_transform()
                + ScaledTranslation(
                    -ACTIVATION_YEAR_LABEL_NUDGE_POINTS / 72,
                    0,
                    figure.dpi_scale_trans,
                )
            )
        elif text == " 26'":
            tick_label.set_transform(
                tick_label.get_transform()
                + ScaledTranslation(
                    ACTIVATION_YEAR_LABEL_NUDGE_POINTS / 72,
                    0,
                    figure.dpi_scale_trans,
                )
            )
    axis.set_xticks(x_positions, minor=True)
    axis.tick_params(axis="x", which="major", length=6)
    axis.tick_params(axis="x", which="minor", length=3, labelbottom=False)
    axis.set_xlim(float(x_positions.min()) - 0.6, float(x_positions.max()) + 0.6)
    axis.set_ylabel(y_axis_title)
    axis.set_title(f"{category_title} ({snapshot_label})")
    axis.set_ylim(0, max(200, int(bar_bottom.max())))
    axis.yaxis.set_major_locator(MaxNLocator(integer=True))
    axis.yaxis.set_minor_locator(MultipleLocator(10))
    axis.tick_params(axis="y", which="minor", length=3)
    axis.grid(axis="y", alpha=0.35)
    axis.grid(axis="x", visible=False)
    axis.set_axisbelow(True)
    match_axis_label_fontsize(axis)
    despine(axis)

    for index, row in enumerate(rows):
        if row.get("period_kind") != "milestone" or index >= len(rows) - 1:
            continue

        boundary_x = (float(x_positions[index]) + float(x_positions[index + 1])) / 2
        axis.axvline(
            boundary_x,
            color="#495057",
            linestyle=(0, (4, 4)),
            linewidth=1,
            alpha=0.9,
            zorder=4,
        )

        milestone_label = _format_milestone_label(str(row.get("milestone_label") or "").strip())
        if milestone_label:
            axis.text(
                boundary_x - 0.08,
                axis.get_ylim()[1] * 0.98,
                milestone_label,
                ha="right",
                va="bottom",
                fontsize=9,
                fontstyle="italic",
                fontweight="normal",
                color="#495057",
                zorder=5,
            )

    if bip2_handles:
        bip2_legend = axis.legend(
            handles=bip2_handles,
            loc="upper left",
            bbox_to_anchor=(1.0, 0.94),
            frameon=False,
            title="BIP2 Status:",
            borderaxespad=0,
            fontsize=9,
            title_fontsize=9.5,
        )
        bip2_legend._legend_box.align = "left"
        axis.add_artist(bip2_legend)

    if bip3_handles:
        bip3_legend = axis.legend(
            handles=bip3_handles,
            loc="upper left",
            bbox_to_anchor=(1.0, 0.30),
            frameon=False,
            title="BIP3 Status:",
            borderaxespad=0,
            fontsize=9,
            title_fontsize=9.5,
        )
        bip3_legend._legend_box.align = "left"

    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, format="pdf", bbox_inches="tight", pad_inches=0.08)
    plt.close(figure)
