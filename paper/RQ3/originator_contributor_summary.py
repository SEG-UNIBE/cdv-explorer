from pathlib import Path

import matplotlib.pyplot as plt

from paper.config import FIGURE_TITLE_FONT_SIZE
from paper.plot_colors import AUTHORS_PER_BIP_COLOR, AUTHORSHIP_DISTRIBUTION_COLOR
from paper.RQ3._plotting import add_bar_label_headroom, save_figure
from paper.RQ3.authorship_overview import (
    _draw_authors_per_bip_axis,
    _draw_authorship_distribution_axis,
    prepare_authors_per_bip,
    prepare_authorship_distribution,
)
from paper.RQ3.contributor_overview import _draw_binned_histogram_axis, _log_bin
from paper.RQ3.originator_contributor_ecdf import (
    CONTRIBUTOR_COLOR,
    ORIGINATOR_COLOR,
    _draw_ecdf_axis,
    _weighted_ecdf,
)

# Width matches the established two-column-spanning convention elsewhere
# (e.g. plot_authorship_overview's (9, 2.8), collaboration_structure_overview's
# (9.2, 2.8)); height scales that same per-row allowance up for 3 rows.
EVALUATION_FIGSIZE = (9.5, 6.5)
# Left column ("X per BIP") needs less room than the right ("BIPs per X"),
# whose x-axis runs to a higher max value for both roles.
COLUMN_WIDTH_RATIOS = (0.35, 0.65)


def plot_originator_contributor_summary(
    originator_bip_count_histogram: list[dict[str, int]],
    contributor_bip_count_histogram: list[dict[str, int]],
    originator_contribution_histogram: list[dict[str, int]],
    contributor_contribution_histogram: list[dict[str, int]],
    output_path: Path,
    snapshot_label: str,
) -> None:
    """3x2 combination of panels already built elsewhere: row 1 is
    authorship_collaboration_triptych.py's originator panels (a)/(b)
    unchanged; row 2 replicates them for contributors using
    contributor_overview.py's power-of-two-binned histogram (an unbinned bar
    chart is illegible here since contributor counts run a far longer tail
    than originator counts); row 3 is originator_contributor_ecdf.py's
    overlay panels."""
    figure, (
        (axis_a, axis_b),
        (axis_c, axis_d),
        (axis_e, axis_f),
    ) = plt.subplots(
        3,
        2,
        figsize=EVALUATION_FIGSIZE,
        gridspec_kw={"width_ratios": COLUMN_WIDTH_RATIOS},
    )

    per_bip_series, per_bip_total = prepare_authors_per_bip(
        originator_bip_count_histogram
    )
    _draw_authors_per_bip_axis(
        axis_a,
        per_bip_series,
        title="(a) Originators per BIP",
        total=per_bip_total,
        entity_label="Originators",
    )
    add_bar_label_headroom(axis_a, ratio=0.12)
    distribution_series, distribution_total = prepare_authorship_distribution(
        originator_contribution_histogram
    )
    _draw_authorship_distribution_axis(
        axis_b,
        distribution_series,
        title="(b) BIPs per Originator",
        total=distribution_total,
        entity_label="Originators",
    )
    add_bar_label_headroom(axis_b)

    contributor_per_bip_labels, contributor_per_bip_counts = _log_bin(
        contributor_bip_count_histogram, "author_count", "bip_count"
    )
    _draw_binned_histogram_axis(
        axis_c,
        contributor_per_bip_labels,
        contributor_per_bip_counts,
        title="(c) Contributors per BIP",
        xlabel="# Contributors",
        ylabel=f"# BIPs ({sum(contributor_per_bip_counts)})",
        color=AUTHORS_PER_BIP_COLOR,
    )
    add_bar_label_headroom(axis_c, ratio=0.12)
    contributor_distribution_labels, contributor_distribution_counts = _log_bin(
        contributor_contribution_histogram, "bips_written", "authors"
    )
    _draw_binned_histogram_axis(
        axis_d,
        contributor_distribution_labels,
        contributor_distribution_counts,
        title="(d) BIPs per Contributor",
        xlabel="# BIPs",
        ylabel=f"# Contributors ({sum(contributor_distribution_counts)})",
        color=AUTHORSHIP_DISTRIBUTION_COLOR,
    )
    add_bar_label_headroom(axis_d)

    _draw_ecdf_axis(
        axis_e,
        [
            (
                "Originators",
                _weighted_ecdf(
                    originator_bip_count_histogram, "author_count", "bip_count"
                ),
                ORIGINATOR_COLOR,
            ),
            (
                "Contributors",
                _weighted_ecdf(
                    contributor_bip_count_histogram, "author_count", "bip_count"
                ),
                CONTRIBUTOR_COLOR,
            ),
        ],
        title="(e) People per BIP",
        xlabel="# People",
    )
    _draw_ecdf_axis(
        axis_f,
        [
            (
                "Originators",
                _weighted_ecdf(
                    originator_contribution_histogram, "bips_written", "authors"
                ),
                ORIGINATOR_COLOR,
            ),
            (
                "Contributors",
                _weighted_ecdf(
                    contributor_contribution_histogram, "bips_written", "authors"
                ),
                CONTRIBUTOR_COLOR,
            ),
        ],
        title="(f) BIPs per Person",
        xlabel="# BIPs",
    )

    figure.suptitle(
        f"Originators vs. Contributors ({snapshot_label})",
        y=1.01,
        fontsize=FIGURE_TITLE_FONT_SIZE,
    )
    figure.tight_layout()
    save_figure(figure, output_path)
