import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.ecosystem_config import ACTIVE_ECOSYSTEM
from paper._utils.io import resolve_output_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Render dependency network plots.")
    parser.add_argument("--snapshot", help="Load a specific snapshot artifact by date (YYYY-MM-DD).")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory where generated PDF plots are written.",
    )
    args = parser.parse_args()

    from analysis.artifact_io import resolve_latest_snapshot_label

    snapshot_label = args.snapshot or resolve_latest_snapshot_label() or "latest"
    default_relative_path = Path(ACTIVE_ECOSYSTEM["postprocess"]) / snapshot_label / "dependencies" / "plots"
    output_dir = resolve_output_dir(args.output_dir, default_relative_path)

    from analysis.artifact_io import load_network_data
    from paper.RQ2.dependency_plots import render_default_dependency_plot_suite

    network_data = load_network_data(snapshot=args.snapshot)
    render_default_dependency_plot_suite(network_data, output_dir=output_dir)


def draw_static_network_with_layouts(*args, **kwargs):
    from paper.RQ2.dependency_plots import draw_static_network_with_layouts as _draw_static_network_with_layouts

    return _draw_static_network_with_layouts(*args, **kwargs)


def render_default_dependency_plot_suite(*args, **kwargs):
    from paper.RQ2.dependency_plots import render_default_dependency_plot_suite as _render_default_dependency_plot_suite

    return _render_default_dependency_plot_suite(*args, **kwargs)


__all__ = ["draw_static_network_with_layouts", "render_default_dependency_plot_suite", "main"]


if __name__ == "__main__":
    main()
