from install_dependencies import install_requirements
from download import download_ips
from preamble_extraction import process_files_and_save_json
from ip_processing import process_ip_files
from ecosystem_config import ACTIVE_ECOSYSTEM
from datetime import date
import argparse
import os
from pathlib import Path
import sys
import time
from analysis.pipeline import prepare_ecosystem_artifacts
from tqdm import tqdm


DEFAULT_SNAPSHOT = "2025-12-31"
HARVEST_ROOT = Path(ACTIVE_ECOSYSTEM["harvest"])
PREPROCESS_ROOT = Path(ACTIVE_ECOSYSTEM["preprocess"])
ANALYSIS_ROOT = Path(ACTIVE_ECOSYSTEM["analysis"])
POSTPROCESS_ROOT = Path(ACTIVE_ECOSYSTEM["postprocess"])


def run_stage(stage_name: str, total: int, unit: str, runner) -> None:
    progress = tqdm(
        total=max(total, 1),
        desc=stage_name,
        unit=unit,
        dynamic_ncols=True,
        file=sys.stdout,
        leave=True,
    )

    def update_stage(message: str | None = None, advance: int = 0) -> None:
        if message:
            progress.set_postfix_str(message)
        if advance:
            progress.update(advance)

    try:
        runner(update_stage)
    finally:
        if progress.n < progress.total:
            progress.update(progress.total - progress.n)
        progress.close()


def main():
    parser = argparse.ArgumentParser(description="Run the full ecosystem pipeline for a specific snapshot.")
    parser.add_argument(
        "--snapshot",
        default=DEFAULT_SNAPSHOT,
        help="Snapshot date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--skipllm",
        action="store_true",
        help="Skip LLM-based implicit dependency extraction and preserve any existing implicit dependencies.",
    )
    args = parser.parse_args()
    snapshot = args.snapshot

    date.fromisoformat(snapshot)

    run_started = time.monotonic()

    # Setup the environment
    run_stage(
        "Install dependencies",
        total=2,
        unit="step",
        runner=lambda update: install_requirements(progress_callback=update),
    )

    input_directory = HARVEST_ROOT
    output_directory = PREPROCESS_ROOT / snapshot

    run_stage(
        "Download repository snapshot",
        total=3,
        unit="step",
        runner=lambda update: download_ips(
            snapshot=snapshot,
            local_dir=input_directory,
            progress_callback=update,
        ),
    )

    # Process files and extract preamble
    proposal_files = [
        name for name in os.listdir(input_directory) if name.endswith((".mediawiki", ".md"))
    ]
    run_stage(
        "Extract preambles",
        total=len(proposal_files),
        unit="ip",
        runner=lambda update: process_files_and_save_json(
            input_directory,
            output_directory,
            file_prefix=ACTIVE_ECOSYSTEM["document_prefix"],
            id_field=ACTIVE_ECOSYSTEM["primary_id_field"],
            progress_callback=update,
        ),
    )

    # Process the metadata and insights
    json_files = [path for path in output_directory.iterdir() if path.suffix == ".json"]
    run_stage(
        "Process metadata and insights",
        total=len(json_files),
        unit="ip",
        runner=lambda update: process_ip_files(
            output_directory,
            output_directory,
            input_directory,
            file_prefix=ACTIVE_ECOSYSTEM["document_prefix"],
            proposal_label=ACTIVE_ECOSYSTEM["proposal_acronym"],
            id_field=ACTIVE_ECOSYSTEM["primary_id_field"],
            skip_llm=args.skipllm,
            progress_callback=update,
        ),
    )

    # Build ecosystem artifacts for visualization consumers.
    run_stage(
        "Build analysis and postprocess artifacts",
        total=7,
        unit="step",
        runner=lambda update: prepare_ecosystem_artifacts(
            proposal_json_dir=output_directory,
            artifact_root=ANALYSIS_ROOT,
            postprocess_root=POSTPROCESS_ROOT,
            snapshot=snapshot,
            id_field=ACTIVE_ECOSYSTEM["primary_id_field"],
            proposal_label=ACTIVE_ECOSYSTEM["proposal_acronym"],
            progress_callback=update,
        ),
    )

    _ = time.monotonic() - run_started

if __name__ == "__main__":
    main()
