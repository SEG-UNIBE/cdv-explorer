from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from paper.RQ3._plotting import add_bar_label_headroom, save_figure
from paper.RQ3.authorship_overview import (
    _draw_authors_per_bip_axis,
    _draw_authorship_distribution_axis,
    prepare_authors_per_bip,
    prepare_authorship_distribution,
)
from paper.RQ3.collaboration_structure_overview import (
    _draw_component_distribution_axis,
    prepare_component_distribution,
)


def plot_authorship_collaboration_triptych(
    contribution_histogram: list[dict[str, int]],
    bip_author_count_histogram: list[dict[str, int]],
    collaboration_network: dict,
    output_path: Path,
) -> None:
    authors_per_bip_series, total_bips = prepare_authors_per_bip(
        bip_author_count_histogram
    )
    authorship_dist_series, total_authors = prepare_authorship_distribution(
        contribution_histogram
    )
    component_series, total_components = prepare_component_distribution(
        collaboration_network
    )

    figure = plt.figure(figsize=(5.0, 5.2))
    grid = figure.add_gridspec(
        2,
        2,
        width_ratios=[
            len(authors_per_bip_series),
            len(component_series),
        ],
        height_ratios=[1.6, 1],
    )
    axis_a = figure.add_subplot(grid[0, 0])
    axis_c = figure.add_subplot(grid[0, 1])
    axis_b = figure.add_subplot(grid[1, :])

    _draw_authors_per_bip_axis(
        axis_a, authors_per_bip_series, title="(a) Authors per BIP", total=total_bips
    )
    add_bar_label_headroom(axis_a, ratio=0.12)

    _draw_authorship_distribution_axis(
        axis_b,
        authorship_dist_series,
        title="(b) BIPs per Author",
        total=total_authors,
    )
    add_bar_label_headroom(axis_b)

    _draw_component_distribution_axis(
        axis_c,
        component_series,
        title="(c) Collaboration Clusters",
        total=total_components,
    )
    add_bar_label_headroom(axis_c)

    figure.tight_layout(pad=0.45, w_pad=1.8, h_pad=1.8)
    save_figure(figure, output_path)


def plot_authorship_collaboration_triptych_row(
    contribution_histogram: list[dict[str, int]],
    bip_author_count_histogram: list[dict[str, int]],
    collaboration_network: dict,
    output_path: Path,
) -> None:
    """Single-row, 3-column variant of the triptych above, sized for a
    two-column-spanning placement (matches the (9.x, 2.8) convention used by
    other wide figures, e.g. authorship_overview's combined panel)."""
    authors_per_bip_series, total_bips = prepare_authors_per_bip(
        bip_author_count_histogram
    )
    authorship_dist_series, total_authors = prepare_authorship_distribution(
        contribution_histogram
    )
    component_series, total_components = prepare_component_distribution(
        collaboration_network
    )

    figure, (axis_a, axis_b, axis_c) = plt.subplots(
        1,
        3,
        figsize=(9.5, 2.8),
        gridspec_kw={
            "width_ratios": [
                len(authors_per_bip_series),
                len(authorship_dist_series),
                len(component_series),
            ]
        },
    )

    _draw_authors_per_bip_axis(
        axis_a, authors_per_bip_series, title="(a) Authors per BIP", total=total_bips
    )
    add_bar_label_headroom(axis_a, ratio=0.12)

    _draw_authorship_distribution_axis(
        axis_b,
        authorship_dist_series,
        title="(b) BIPs per Author",
        total=total_authors,
    )
    add_bar_label_headroom(axis_b)

    _draw_component_distribution_axis(
        axis_c,
        component_series,
        title="(c) Collaboration Clusters",
        total=total_components,
    )
    add_bar_label_headroom(axis_c)

    figure.tight_layout(pad=0.45, w_pad=1.8)
    save_figure(figure, output_path)
