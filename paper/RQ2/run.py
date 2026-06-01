import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from paper.config import SNAPSHOT
from paper._utils.io import resolve_output_dir, snapshot_prefix

# Set this directly only when RQ2 needs a custom output location.
OUTPUT_DIR = None
GENERATE_DEPENDENCY_PLOTS = False
GENERATE_DIFFERENTIAL_DEPENDENCY_PLOTS = True
GENERATE_DEPENDENCY_COMPARISON_TABLE = True
GENERATE_CENTRALITY_TOP5_TABLE = True
DIFFERENTIAL_FOCUS_BIPS = [67,93,350,77]
EXCLUDE_BIPS = [174,21,78,324]

DIFFERENTIAL_LAYOUT = "kamada_kawai"
DIFFERENTIAL_LAYOUT_EXPORT = Path("paper") / "RQ2" / "dependency_layout_260316_67_93_350.json"
DIFFERENTIAL_LAYOUT_EXPORT_LABEL = "react"
DIFFERENTIAL_ALTERNATIVE_LAYOUTS = ["spring_scaled", "planar", "spectral", "shell", "circular", "bipartite", "multipartite"]


def main() -> None:
    from analysis.artifact_io import load_network_data, load_dependency_metrics, resolve_latest_snapshot_label
    from paper.RQ2.dependency_differential_plots import render_differential_dependency_plots
    from paper.RQ2.dependency_plots import render_default_dependency_plot_suite
    from paper.RQ2.dependency_comparison_table import (
        export_dependency_comparison_latex_table,
        export_preamble_dependency_comparison_latex_table,
        export_preamble_plus_regex_llm_dependency_comparison_latex_table,
    )
    from paper.RQ2.dependency_centrality_table import export_centrality_top5_latex_table

    snapshot_label = SNAPSHOT or resolve_latest_snapshot_label() or "latest"
    default_relative_path = Path("paper") / "RQ2" / "outputs"
    output_dir = resolve_output_dir(OUTPUT_DIR, default_relative_path)
    filename_prefix = snapshot_prefix(snapshot_label)

    network_data = load_network_data(snapshot=SNAPSHOT)
    dep_metrics = load_dependency_metrics(snapshot=SNAPSHOT)
    if GENERATE_DEPENDENCY_PLOTS:
        render_default_dependency_plot_suite(
            network_data,
            output_dir=output_dir,
            filename_prefix=filename_prefix,
        )
    if GENERATE_DIFFERENTIAL_DEPENDENCY_PLOTS:
        if DIFFERENTIAL_LAYOUT_EXPORT:
            render_differential_dependency_plots(
                network_data,
                output_dir=output_dir,
                filename_prefix=filename_prefix,
                focus_bips=DIFFERENTIAL_FOCUS_BIPS,
                exclude_bips=EXCLUDE_BIPS,
                layout_name=DIFFERENTIAL_LAYOUT_EXPORT_LABEL,
                layout_export_path=Path(DIFFERENTIAL_LAYOUT_EXPORT),
            )
        else: 
            render_differential_dependency_plots(
                network_data,
                output_dir=output_dir,
                filename_prefix=filename_prefix,
                focus_bips=DIFFERENTIAL_FOCUS_BIPS,
                exclude_bips=EXCLUDE_BIPS,
                layout_name=DIFFERENTIAL_LAYOUT,
            )
            for alt_layout in DIFFERENTIAL_ALTERNATIVE_LAYOUTS:
                render_differential_dependency_plots(
                    network_data,
                    output_dir=output_dir,
                    filename_prefix=filename_prefix,
                    focus_bips=DIFFERENTIAL_FOCUS_BIPS,
                    exclude_bips=EXCLUDE_BIPS,
                    layout_name=alt_layout,
                    )
    if GENERATE_CENTRALITY_TOP5_TABLE:
        export_centrality_top5_latex_table(
            dep_metrics=dep_metrics,
            output_path=output_dir / f"{filename_prefix}_centrality_top5.tex",
        )
    if GENERATE_DEPENDENCY_COMPARISON_TABLE:
        export_dependency_comparison_latex_table(
            network_data=network_data,
            output_path=output_dir / f"{filename_prefix}_dependency_pairwise_comparison.tex",
        )
        export_preamble_dependency_comparison_latex_table(
            network_data=network_data,
            output_path=output_dir / f"{filename_prefix}_dependency_pairwise_comparison_preamble_only.tex",
        )
        export_preamble_plus_regex_llm_dependency_comparison_latex_table(
            network_data=network_data,
            output_path=output_dir / f"{filename_prefix}_dependency_pairwise_comparison_preamble_plus_regex_llm.tex",
        )


if __name__ == "__main__":
    main()
