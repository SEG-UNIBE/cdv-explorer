from pathlib import Path
from typing import Any

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator, MultipleLocator

from paper.config import FIGURE_TITLE_FONT_SIZE
from paper.plot_colors import REACT_CLASSIFICATION_PALETTE, tint
from paper.RQ3._plotting import (
    BAR_EDGE_COLOR,
    bar_style,
    despine,
    match_axis_label_fontsize,
)

ACTIVATION_GAP = 0.45
TITLE_PAD = 12
BAR_WIDTH = 0.82
EVOLUTION_BAR_EDGE_WIDTH = 0.5
LEGEND_FONT_SIZE = 8.25
LEGEND_TITLE_FONT_SIZE = 8.75
LEGEND_LABEL_SPACING = 0.35
LEGEND_SECTION_TOP = 1.0
LEGEND_SECTION_BOTTOM = 0.01
# Deliberately distinct from classification_status.STATUS_COLORS: this chart
# stacks many statuses per bar and needs maximum adjacent-color separation.
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


def _react_color_map(categories: list[str]) -> dict[str, tuple]:
    return {
        category: tint(
            FIXED_STATUS_COLORS.get(
                category,
                REACT_CLASSIFICATION_PALETTE[index % len(REACT_CLASSIFICATION_PALETTE)],
            )
        )
        for index, category in enumerate(categories)
    }


def _format_period_display_label(period_key: str, period_label: str) -> str:
    if "-pre-" in period_key:
        return f"{period_label}a"
    if "-post-" in period_key:
        return f"{period_label}b"
    return period_label


# The milestone annotation names its own activation date directly (no
# separate "16"/"16'" split tick labels; see _select_tick_positions).
MILESTONE_ACTIVATION_DATE_LABELS = {
    "2": "Nov 16",
    "3": "Jan 26",
}


def _format_milestone_label(label: str) -> str:
    text = label.strip()
    if text.startswith("BIP") and text.endswith(" Activation"):
        number = text[3:-11]
        if number.isdigit():
            date_label = MILESTONE_ACTIVATION_DATE_LABELS.get(number)
            if date_label:
                return f"BIP{number} activation ({date_label})"
            return f"BIP-{number} activation"
    return text


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
        category for category in preferred_categories if category in observed_categories
    ]
    ordered_categories.extend(
        category
        for category in observed_categories
        if category not in ordered_categories
    )
    if not ordered_categories:
        raise ValueError(
            "Status evolution plot requires at least one positive status count."
        )

    periods = [row["period"] for row in rows]
    series = {
        category: [int(row["values"].get(category, 0)) for row in rows]
        for category in ordered_categories
    }
    return periods, ordered_categories, series


def _normalize_segmented_rows(
    status_evolution_segmented: dict[str, Any] | None,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[str],
    dict[str, list[int]],
    list[dict[str, Any]],
    bool,
]:
    segmented = status_evolution_segmented or {}
    raw_segment_definitions = segmented.get("segmentDefinitions") or []
    raw_rows = segmented.get("rows") or []
    if not raw_segment_definitions or not raw_rows:
        raise ValueError("Segmented evolution data is unavailable.")

    rows = [
        {
            "period_key": str(
                row.get("period_key") or row.get("period") or row.get("year") or ""
            ).strip(),
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
        if str(
            row.get("period_key") or row.get("period") or row.get("year") or ""
        ).strip()
    ]
    if not rows:
        raise ValueError("Segmented evolution data is missing rows.")

    rows.sort(key=lambda row: (row["period_end"], row["index"]))

    segment_definitions = [
        {
            "key": str(segment.get("key") or "").strip(),
            "status": str(segment.get("status") or "").strip(),
            "standard": str(segment.get("standard") or "").strip(),
            "standard_label": str(segment.get("standardLabel") or "").strip(),
            "is_official": bool(segment.get("isOfficial", True)),
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
        raise ValueError(
            "Segmented evolution plot requires at least one positive segment."
        )

    ordered_statuses = list(
        dict.fromkeys(segment["status"] for segment in visible_segment_definitions)
    )
    segment_series = {
        segment["key"]: [int(row["values"].get(segment["key"], 0)) for row in rows]
        for segment in visible_segment_definitions
    }
    legend_sections: list[dict[str, Any]] = []
    for segment in visible_segment_definitions:
        standard = segment["standard"]
        section = next(
            (entry for entry in legend_sections if entry["key"] == standard), None
        )
        if section is None:
            section = {
                "key": standard,
                "label": segment["standard_label"]
                or (standard.upper() if standard else ""),
                "segments": [],
            }
            legend_sections.append(section)
        section["segments"].append(segment)

    for row in rows:
        row["display_label"] = _format_period_display_label(
            row["period_key"], row["period"]
        )

    has_non_official = any(
        not segment["is_official"] for segment in visible_segment_definitions
    )
    return (
        rows,
        visible_segment_definitions,
        ordered_statuses,
        segment_series,
        legend_sections,
        has_non_official,
    )


def _build_period_positions(rows: list[dict[str, Any]]) -> np.ndarray:
    positions: list[float] = []
    current_position = 0.0
    for index, row in enumerate(rows):
        positions.append(current_position)
        current_position += 1.0
        if row.get("period_kind") == "milestone" and index < len(rows) - 1:
            current_position += ACTIVATION_GAP
    return np.array(positions, dtype=float)


def _select_tick_positions(
    rows: list[dict[str, Any]], x_positions: np.ndarray
) -> tuple[np.ndarray, list[str]]:
    # Each year's tick aligns with its first bar (Q1, or Q1's pre-activation
    # half if a milestone splits it) rather than some average/midpoint of
    # that year's bars. A milestone stretches its split quarter's footprint,
    # which pulled any average- or midpoint-based tick off-center or onto a
    # bar; anchoring to a fixed, always-present bar (the year's first) is
    # simple and consistent for every year regardless of milestones or
    # partial data at the run's start/end.
    positions_by_year: dict[str, float] = {}
    year_order: list[str] = []
    for index, row in enumerate(rows):
        period_label = str(row.get("period") or "").strip()
        if not period_label or "-" not in period_label:
            continue
        year = period_label.split("-", 1)[0]
        if year not in positions_by_year:
            year_order.append(year)
            positions_by_year[year] = float(x_positions[index])

    if year_order:
        tick_labels = year_order
        tick_positions = [positions_by_year[year] for year in tick_labels]
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
        (
            rows,
            visible_segment_definitions,
            ordered_statuses,
            segment_series,
            legend_sections,
            has_non_official,
        ) = _normalize_segmented_rows(
            status_evolution_segmented,
        )
        plot_segments = list(visible_segment_definitions)
    except ValueError:
        periods, ordered_statuses, series = _normalize_evolution_series(
            status_evolution
        )
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
                "key": status,
                "status": status,
                "standard": "",
                "standard_label": "",
                "is_official": True,
            }
            for status in ordered_statuses
        ]
        segment_series = {status: counts for status, counts in series.items()}
        legend_sections = [{"key": "all", "label": "", "segments": plot_segments}]
        has_non_official = False

    x_positions = _build_period_positions(rows)
    color_map = _react_color_map(ordered_statuses)

    bar_bottom = np.zeros(len(rows), dtype=int)
    figure, axis = plt.subplots(figsize=(10.0, 4.8))

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
                **_evolution_bar_style(color_map[segment["status"]]),
            )
        bar_bottom = bar_bottom + counts

    major_tick_positions, major_tick_labels = _select_tick_positions(rows, x_positions)
    axis.set_xticks(major_tick_positions)
    axis.set_xticklabels(major_tick_labels, rotation=0, ha="center")
    axis.set_xticks(x_positions, minor=True)
    axis.tick_params(axis="x", which="major", length=6)
    axis.tick_params(axis="x", which="minor", length=3, labelbottom=False)
    axis.set_xlim(float(x_positions.min()) - 0.6, float(x_positions.max()) + 0.6)
    axis.set_ylabel(y_axis_title)
    axis.set_title(
        f"{category_title} ({snapshot_label})",
        fontsize=FIGURE_TITLE_FONT_SIZE,
        pad=TITLE_PAD,
    )
    axis.set_ylim(0, max(200, int(bar_bottom.max())))
    axis.yaxis.set_major_locator(MaxNLocator(integer=True))
    axis.yaxis.set_minor_locator(MultipleLocator(10))
    axis.tick_params(axis="y", which="minor", length=3)
    axis.grid(axis="y", alpha=0.35)
    axis.grid(axis="x", visible=False)
    axis.set_axisbelow(True)
    match_axis_label_fontsize(axis)
    despine(axis)

    if has_non_official:
        figure.text(
            0.01,
            0.01,
            "* non-official status labels observed in repository history",
            ha="left",
            va="bottom",
            fontsize=8.5,
            color="#495057",
        )

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

        milestone_label = _format_milestone_label(
            str(row.get("milestone_label") or "").strip()
        )
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

    rendered_legends = []
    for section in legend_sections:
        handles = [
            Patch(
                facecolor=_evolution_bar_style(color_map[segment["status"]])["color"],
                edgecolor=BAR_EDGE_COLOR,
                linewidth=EVOLUTION_BAR_EDGE_WIDTH,
                label=f"{segment['status']}*"
                if not segment.get("is_official", True)
                else segment["status"],
            )
            for segment in reversed(section["segments"])
        ]
        if not handles:
            continue
        legend = axis.legend(
            handles=handles,
            loc="upper left",
            bbox_to_anchor=(1.0, LEGEND_SECTION_TOP),
            frameon=False,
            title=f"{section['label']} Status:" if section["label"] else None,
            borderaxespad=0,
            fontsize=LEGEND_FONT_SIZE,
            title_fontsize=LEGEND_TITLE_FONT_SIZE,
            labelspacing=LEGEND_LABEL_SPACING,
        )
        legend._legend_box.align = "left"
        rendered_legends.append(legend)

    if len(rendered_legends) > 1:
        figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
        legend_heights = [
            axis.transAxes.inverted()
            .transform_bbox(legend.get_window_extent(renderer))
            .height
            for legend in rendered_legends
        ]
        available_height = LEGEND_SECTION_TOP - LEGEND_SECTION_BOTTOM
        total_legend_height = sum(legend_heights)
        section_gap = max(
            0.0, (available_height - total_legend_height) / (len(rendered_legends) - 1)
        )

        current_top = LEGEND_SECTION_TOP
        for legend, legend_height in zip(
            rendered_legends, legend_heights, strict=False
        ):
            legend.set_bbox_to_anchor((1.0, current_top), transform=axis.transAxes)
            current_top -= legend_height + section_gap

    for legend in rendered_legends[:-1]:
        axis.add_artist(legend)

    figure.tight_layout(rect=(0, 0.04 if has_non_official else 0, 1, 1))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, format="pdf", bbox_inches="tight", pad_inches=0.08)
    plt.close(figure)
