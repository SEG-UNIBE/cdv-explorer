from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from paper.RQ3._plotting import add_bar_label_headroom, save_figure
from paper.RQ3.authorship_overview import (
    _draw_authors_per_bip_axis,
    _draw_authorship_distribution_axis,
    _draw_top_authors_axis,
    _prepare_top_ten,
    prepare_authors_per_bip,
    prepare_authorship_distribution,
)
from paper.RQ3.collaboration_structure_overview import (
    _draw_component_distribution_axis,
    prepare_component_distribution,
)


def plot_authorship_collaboration_quartet(
    contribution_histogram: list[dict[str, int]],
    bip_author_count_histogram: list[dict[str, int]],
    collaboration_network: dict,
    top_authors: list[dict[str, int | str]],
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
    top_ten = _prepare_top_ten(top_authors)

    figure = plt.figure(figsize=(7.8, 5.2))
    grid = figure.add_gridspec(
        2,
        2,
        width_ratios=[1, 1.5],
    )
    axis_a = figure.add_subplot(grid[0, 0])
    axis_b = figure.add_subplot(grid[0, 1])
    axis_c = figure.add_subplot(grid[1, 0])
    axis_d = figure.add_subplot(grid[1, 1])

    _draw_top_authors_axis(axis_a, top_ten, title="(a) Top 10 Authors")

    _draw_component_distribution_axis(
        axis_b,
        component_series,
        title="(b) Collaboration Clusters",
        total=total_components,
    )
    add_bar_label_headroom(axis_b)

    _draw_authors_per_bip_axis(
        axis_c, authors_per_bip_series, title="(c) Authors per BIP", total=total_bips
    )
    add_bar_label_headroom(axis_c, ratio=0.12)

    _draw_authorship_distribution_axis(
        axis_d,
        authorship_dist_series,
        title="(d) BIPs per Author",
        total=total_authors,
    )
    add_bar_label_headroom(axis_d)

    figure.tight_layout(pad=0.45, w_pad=1.8, h_pad=1.8)
    save_figure(figure, output_path)
