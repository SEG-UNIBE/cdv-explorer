import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from paper._utils.io import resolve_output_dir, snapshot_prefix
from paper.config import SNAPSHOT

# Set this directly only when RQ3 needs a custom output location.
OUTPUT_DIR = None


def main() -> None:
    from analysis.artifact_io import (
        load_centrality_comparison,
        resolve_latest_snapshot_label,
    )
    from paper.RQ3.centrality_concordance_table import (
        export_centrality_concordance_latex_table,
    )
    from paper.RQ3.dependency_centrality_table import (
        export_centrality_top5_latex_table,
    )

    snapshot_label = SNAPSHOT or resolve_latest_snapshot_label() or "latest"
    output_dir = resolve_output_dir(OUTPUT_DIR, Path("paper") / "RQ3" / "outputs")
    filename_prefix = snapshot_prefix(snapshot_label)

    centrality_comparison = load_centrality_comparison(snapshot=SNAPSHOT)
    export_centrality_top5_latex_table(
        centrality_comparison=centrality_comparison,
        output_path=output_dir / f"{filename_prefix}_centrality_top5.tex",
    )
    export_centrality_concordance_latex_table(
        centrality_comparison=centrality_comparison,
        output_path=output_dir / f"{filename_prefix}_centrality_concordance.tex",
    )


if __name__ == "__main__":
    main()
