import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from paper._utils.io import resolve_output_dir, snapshot_prefix
from paper.config import SNAPSHOT

# Set this directly only when RQ2 needs a custom output location.
OUTPUT_DIR = None
GENERATE_DEPENDENCY_PLOTS = False
GENERATE_DIFFERENTIAL_DEPENDENCY_PLOTS = True
GENERATE_DEPENDENCY_COMPARISON_TABLE = True
GENERATE_CENTRALITY_TOP5_TABLE = True
GENERATE_GROUND_TRUTH_EVALUATION_PLOT = True
GENERATE_TYPE_MAPPING_TABLE = True
GENERATE_GROUND_TRUTH_DATASET_TABLE = True
DIFFERENTIAL_FALLBACK_FOCUS_BIPS = [20, 67, 77, 78, 93, 321, 350, 433]
DIFFERENTIAL_FALLBACK_EXCLUDE_BIPS = [79, 324, 21, 353, 13, 392, 451]
DIFFERENTIAL_HIGHLIGHT_BIPS_PREAMBLE_VS_REGEX = [77, 173, 67, 16, 48, 123, 20]
DIFFERENTIAL_HIGHLIGHT_BIPS_REGEX_VS_LLM: list[int] = [48, 67, 350, 341, 77, 173, 78, 174, 32, 39, 321, 20]
DIFFERENTIAL_HIGHLIGHT_BIPS_BY_SUBPLOT = (
    DIFFERENTIAL_HIGHLIGHT_BIPS_PREAMBLE_VS_REGEX,
    DIFFERENTIAL_HIGHLIGHT_BIPS_REGEX_VS_LLM,
)
# This directed edge set defines both the visible nodes and the plotted edges.
# The layout export below supplies coordinates only.
DIFFERENTIAL_INCLUDE_EDGES = [
    (32, 39),
    (48, 67),
    (67, 11),
    (67, 16),
    (67, 45),
    (77, 78),
    (77, 173),
    (77, 174),
    (77, 321),
    (78, 174),
    (87, 67),
    (93, 32),
    (93, 39),
    (93, 173),
    (118, 350),
    (123, 20),
    (123, 67),
    (128, 433),
    (136, 350),
    (173, 350),
    (321, 20),
    (321, 173),
    (321, 350),
    (321, 351),
    (321, 352),
    (341, 350),
    (347, 340),
    (347, 341),
    (350, 141),
    (350, 173),
    (350, 341),
    (351, 350),
    (352, 350),
    (360, 350),
    (433, 141),
    (433, 350),
    (433, 431),
]

DIFFERENTIAL_LAYOUT = "kamada_kawai"
DIFFERENTIAL_LAYOUT_EXPORT = (
    Path("paper")
    / "RQ2"
    / "dependency_layout_260630_BIP20_BIP67_BIP77_BIP78_BIP93_BIP321_BIP347_BIP350_BIP433.json"
)
DIFFERENTIAL_LAYOUT_EXPORT_LABEL = "react"
DIFFERENTIAL_ALTERNATIVE_LAYOUTS = [
    "spring_scaled",
    "planar",
    "spectral",
    "shell",
    "circular",
    "bipartite",
    "multipartite",
]


def main() -> None:
    from analysis.artifact_io import (
        load_dependency_metrics,
        load_network_data,
        resolve_latest_snapshot_label,
    )
    from paper.RQ2.dependency_centrality_table import export_centrality_top5_latex_table
    from paper.RQ2.dependency_comparison_table import (
        export_dependency_comparison_latex_table,
        export_preamble_dependency_comparison_latex_table,
        export_preamble_plus_regex_llm_dependency_comparison_latex_table,
    )
    from paper.RQ2.dependency_differential_plots import (
        render_differential_dependency_plots,
    )
    from paper.RQ2.dependency_plots import render_default_dependency_plot_suite
    from paper.RQ2.dependency_type_mapping_table import (
        export_type_mapping_latex_table,
    )
    from paper.RQ2.ground_truth_dataset_table import (
        export_ground_truth_dataset_latex_table,
    )
    from paper.RQ2.ground_truth_evaluation import (
        plot_ground_truth_evaluation_combined,
        plot_ground_truth_evaluation_doe,
        plot_ground_truth_evaluation_eta,
    )

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
                include_edges=DIFFERENTIAL_INCLUDE_EDGES,
                highlight_bips_by_subplot=DIFFERENTIAL_HIGHLIGHT_BIPS_BY_SUBPLOT,
                layout_name=DIFFERENTIAL_LAYOUT_EXPORT_LABEL,
                layout_export_path=Path(DIFFERENTIAL_LAYOUT_EXPORT),
            )
        else:
            render_differential_dependency_plots(
                network_data,
                output_dir=output_dir,
                filename_prefix=filename_prefix,
                highlight_bips_by_subplot=DIFFERENTIAL_HIGHLIGHT_BIPS_BY_SUBPLOT,
                focus_bips=DIFFERENTIAL_FALLBACK_FOCUS_BIPS,
                exclude_bips=DIFFERENTIAL_FALLBACK_EXCLUDE_BIPS,
                layout_name=DIFFERENTIAL_LAYOUT,
            )
            for alt_layout in DIFFERENTIAL_ALTERNATIVE_LAYOUTS:
                render_differential_dependency_plots(
                    network_data,
                    output_dir=output_dir,
                    filename_prefix=filename_prefix,
                    highlight_bips_by_subplot=DIFFERENTIAL_HIGHLIGHT_BIPS_BY_SUBPLOT,
                    focus_bips=DIFFERENTIAL_FALLBACK_FOCUS_BIPS,
                    exclude_bips=DIFFERENTIAL_FALLBACK_EXCLUDE_BIPS,
                    layout_name=alt_layout,
                )
    if GENERATE_GROUND_TRUTH_EVALUATION_PLOT:
        plot_ground_truth_evaluation_doe(
            network_data=network_data,
            output_path=output_dir / f"{filename_prefix}_GT_eval_DOE.pdf",
            snapshot_label=snapshot_label,
        )
        plot_ground_truth_evaluation_eta(
            network_data=network_data,
            output_path=output_dir / f"{filename_prefix}_GT_eval_ETA.pdf",
            snapshot_label=snapshot_label,
        )
        plot_ground_truth_evaluation_combined(
            network_data=network_data,
            output_path=output_dir / f"{filename_prefix}_GT_eval_combined.pdf",
            snapshot_label=snapshot_label,
        )
    if GENERATE_CENTRALITY_TOP5_TABLE:
        export_centrality_top5_latex_table(
            dep_metrics=dep_metrics,
            output_path=output_dir / f"{filename_prefix}_centrality_top5.tex",
        )
    if GENERATE_DEPENDENCY_COMPARISON_TABLE:
        export_dependency_comparison_latex_table(
            network_data=network_data,
            output_path=output_dir
            / f"{filename_prefix}_dependency_pairwise_comparison.tex",
        )
        export_preamble_dependency_comparison_latex_table(
            network_data=network_data,
            output_path=output_dir
            / f"{filename_prefix}_dependency_pairwise_comparison_preamble_only.tex",
        )
        export_preamble_plus_regex_llm_dependency_comparison_latex_table(
            network_data=network_data,
            output_path=output_dir
            / f"{filename_prefix}_dependency_pairwise_comparison_preamble_plus_regex_llm.tex",
        )
    if GENERATE_TYPE_MAPPING_TABLE:
        export_type_mapping_latex_table(
            network_data=network_data,
            output_path=output_dir / f"{filename_prefix}_ground_truth_type_mapping.tex",
        )
    if GENERATE_GROUND_TRUTH_DATASET_TABLE:
        export_ground_truth_dataset_latex_table(
            network_data=network_data,
            output_path=output_dir
            / f"{filename_prefix}_ground_truth_dataset_composition.tex",
        )


if __name__ == "__main__":
    main()
