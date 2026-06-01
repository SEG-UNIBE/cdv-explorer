from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from paper.RQ3._plotting import add_bar_label_headroom, save_figure
from paper.RQ3.authorship_overview import (
    _draw_authorship_distribution_axis,
    _draw_authors_per_bip_axis,
    prepare_authorship_distribution,
    prepare_authors_per_bip,
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
    authors_per_bip_series, total_bips = prepare_authors_per_bip(bip_author_count_histogram)
    authorship_dist_series, total_authors = prepare_authorship_distribution(contribution_histogram)
    component_series, total_components = prepare_component_distribution(collaboration_network)

    figure, axes = plt.subplots(
        1,
        3,
        figsize=(9.2, 2.8),
        gridspec_kw={"width_ratios": [len(authors_per_bip_series), len(authorship_dist_series), len(component_series)]},
    )

    _draw_authors_per_bip_axis(axes[0], authors_per_bip_series, title="(a) Authors per BIP", total=total_bips)
    add_bar_label_headroom(axes[0], ratio=0.12)

    _draw_authorship_distribution_axis(axes[1], authorship_dist_series, title="(b) BIPs per Author", total=total_authors)
    add_bar_label_headroom(axes[1])

    _draw_component_distribution_axis(axes[2], component_series, title="(c) Collaboration Clusters", total=total_components)
    add_bar_label_headroom(axes[2])

    figure.tight_layout(pad=0.45, w_pad=0.7)
    save_figure(figure, output_path)
