from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from paper.RQ3._plotting import (
    bar_style,
    despine,
    match_axis_label_fontsize,
    save_figure,
    style_ellipsis_ticklabels,
)
from paper.RQ3.collaboration_common import (
    build_collaboration_component_size_distribution,
    build_collaboration_degree_distribution,
)
from paper.plot_colors import COLLABORATION_COMPONENT_COLOR


COMPONENT_BAR_COLOR = COLLABORATION_COMPONENT_COLOR
DEGREE_BAR_COLOR = "#4c78a8"
MIN_COMPRESSED_GAP_LENGTH = 2
COMPONENT_GAP_LABEL = "..."


def _expand_integer_series(
    points: list[dict[str, int]],
    *,
    x_key: str,
    y_key: str,
) -> list[dict[str, int]]:
    if not points:
        return []

    sorted_points = sorted(points, key=lambda entry: int(entry[x_key]))
    min_x = int(sorted_points[0][x_key])
    max_x = int(sorted_points[-1][x_key])
    y_by_x = {
        int(entry[x_key]): int(entry[y_key])
        for entry in sorted_points
    }

    return [
        {
            x_key: x_value,
            y_key: int(y_by_x.get(x_value, 0)),
        }
        for x_value in range(min_x, max_x + 1)
    ]


def _compress_zero_gaps(
    series: list[dict[str, int]],
    *,
    x_key: str,
    y_key: str,
    min_gap_length: int = MIN_COMPRESSED_GAP_LENGTH,
) -> list[dict[str, int | str | bool]]:
    if not series:
        return []

    zero_runs: list[tuple[int, int]] = []
    run_start: int | None = None

    for index, entry in enumerate(series):
        if int(entry[y_key]) == 0:
            if run_start is None:
                run_start = index
            continue

        if run_start is not None:
            zero_runs.append((run_start, index - 1))
            run_start = None

    if run_start is not None:
        zero_runs.append((run_start, len(series) - 1))

    eligible_runs = [
        (start, end)
        for start, end in zero_runs
        if (end - start + 1) >= min_gap_length
    ]
    if not eligible_runs:
        return [
            {
                **entry,
                "axis_label": str(int(entry[x_key])),
                "is_gap": False,
            }
            for entry in series
        ]

    compressed = []
    for index, entry in enumerate(series):
        matching_run = next(
            (
                (start, end)
                for start, end in eligible_runs
                if start <= index <= end
            ),
            None,
        )
        if matching_run is None:
            compressed.append(
                {
                    **entry,
                    "axis_label": str(int(entry[x_key])),
                    "is_gap": False,
                }
            )
            continue

        gap_start, _gap_end = matching_run
        if index == gap_start:
            compressed.append(
                {
                    x_key: -1,
                    y_key: 0,
                    "axis_label": COMPONENT_GAP_LABEL,
                    "is_gap": True,
                }
            )

    return compressed


def _prepare_component_and_degree_series(
    collaboration_network: dict,
) -> tuple[list[dict[str, int | str | bool]], list[dict[str, int]]]:
    component_distribution = build_collaboration_component_size_distribution(collaboration_network)
    degree_distribution = build_collaboration_degree_distribution(collaboration_network)

    if not component_distribution:
        raise ValueError("Collaboration structure overview requires non-empty component-size data.")
    if not degree_distribution:
        raise ValueError("Collaboration structure overview requires non-empty degree-distribution data.")

    full_component_series = _expand_integer_series(
        component_distribution,
        x_key="cluster_size",
        y_key="cluster_count",
    )
    displayed_component_series = _compress_zero_gaps(
        full_component_series,
        x_key="cluster_size",
        y_key="cluster_count",
    )

    full_degree_series = _expand_integer_series(
        degree_distribution,
        x_key="degree",
        y_key="author_count",
    )

    return displayed_component_series, full_degree_series


def prepare_component_distribution(
    collaboration_network: dict,
) -> tuple[list[dict[str, int | str | bool]], int]:
    displayed_component_series, _ = _prepare_component_and_degree_series(collaboration_network)
    total = sum(int(e["cluster_count"]) for e in displayed_component_series if "cluster_count" in e)
    return displayed_component_series, total


def _draw_component_distribution_axis(
    axis,
    displayed_component_series: list[dict[str, int | str | bool]],
    *,
    title: str | None,
    total: int | None = None,
) -> None:
    component_positions = np.arange(len(displayed_component_series))
    component_counts = [int(entry["cluster_count"]) for entry in displayed_component_series]
    component_labels = [str(entry["axis_label"]) for entry in displayed_component_series]

    axis.bar(
        component_positions,
        component_counts,
        width=0.82,
        zorder=2,
        **bar_style(COMPONENT_BAR_COLOR),
    )

    component_max = max(component_counts) if component_counts else 0
    component_label_offset = max(component_max * 0.015, 0.15)

    if title:
        axis.set_title(title)
    axis.set_xlabel("# Authors in component")
    axis.set_ylabel("# Connected components" if total is None else f"# Connected components ({total})")
    axis.set_xticks(component_positions)
    axis.set_xticklabels(component_labels)
    axis.set_xlim(-0.6, len(component_positions) - 0.4)
    axis.set_ylim(0, component_max * 1.16 if component_max > 0 else 1)
    axis.grid(axis="y", alpha=0.35)
    axis.grid(axis="x", visible=False)
    match_axis_label_fontsize(axis)
    for x_position, count, entry in zip(component_positions, component_counts, displayed_component_series):
        if count <= 0 or bool(entry.get("is_gap")):
            continue
        axis.text(
            x_position,
            count + component_label_offset,
            str(count),
            ha="center",
            va="bottom",
        )
    style_ellipsis_ticklabels(
        axis,
        component_labels,
        ellipsis_label=COMPONENT_GAP_LABEL,
    )
    despine(axis)


def _draw_degree_distribution_axis(
    axis,
    full_degree_series: list[dict[str, int]],
    *,
    title: str | None,
) -> None:
    degree_positions = np.arange(len(full_degree_series))
    degree_counts = [int(entry["author_count"]) for entry in full_degree_series]
    degree_labels = [str(int(entry["degree"])) for entry in full_degree_series]
    degree_max = max(degree_counts) if degree_counts else 0
    degree_label_offset = max(degree_max * 0.015, 0.15)

    axis.bar(
        degree_positions,
        degree_counts,
        width=0.82,
        zorder=2,
        **bar_style(DEGREE_BAR_COLOR),
    )
    if title:
        axis.set_title(title)
    axis.set_xlabel("Distinct co-authors per author")
    axis.set_ylabel("Number of authors")
    axis.set_xticks(degree_positions)
    axis.set_xticklabels(degree_labels)
    axis.set_xlim(-0.6, len(degree_positions) - 0.4)
    axis.set_ylim(0, degree_max * 1.16 if degree_max > 0 else 1)
    axis.grid(axis="y", alpha=0.35)
    axis.grid(axis="x", visible=False)
    match_axis_label_fontsize(axis)
    for x_position, count in zip(degree_positions, degree_counts):
        if count <= 0:
            continue
        axis.text(
            x_position,
            count + degree_label_offset,
            str(count),
            ha="center",
            va="bottom",
        )
    despine(axis)


def plot_connected_component_size_distribution(
    collaboration_network: dict,
    output_path: Path,
) -> None:
    displayed_component_series, _ = _prepare_component_and_degree_series(collaboration_network)
    figure, axis = plt.subplots(figsize=(3.6, 2.8))
    _draw_component_distribution_axis(axis, displayed_component_series, title=None)
    figure.tight_layout()
    save_figure(figure, output_path)


def plot_coauthor_degree_distribution(
    collaboration_network: dict,
    output_path: Path,
) -> None:
    _, full_degree_series = _prepare_component_and_degree_series(collaboration_network)
    figure, axis = plt.subplots(figsize=(4.4, 2.8))
    _draw_degree_distribution_axis(axis, full_degree_series, title=None)
    figure.tight_layout()
    save_figure(figure, output_path)


def plot_collaboration_structure_overview(
    collaboration_network: dict,
    output_path: Path,
    snapshot_label: str,
) -> None:
    displayed_component_series, full_degree_series = _prepare_component_and_degree_series(collaboration_network)

    figure, (axis_left, axis_right) = plt.subplots(
        1,
        2,
        figsize=(9.2, 2.8),
    )

    _draw_component_distribution_axis(
        axis_left,
        displayed_component_series,
        title="(a) Connected Component Size Distribution",
    )
    _draw_degree_distribution_axis(
        axis_right,
        full_degree_series,
        title="(b) Co-Author Degree Distribution",
    )

    figure.suptitle(f"Collaboration Structure Overview ({snapshot_label})", y=1.02)
    figure.tight_layout()
    save_figure(figure, output_path)
