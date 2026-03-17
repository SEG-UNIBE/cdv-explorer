from install_dependencies import install_requirements
from download import download_ips
from preamble_extraction import process_files_and_save_json
from ip_processing import process_ip_files
from ecosystem_config import ACTIVE_ECOSYSTEM
from datetime import date
import argparse
from pathlib import Path
import time
from analysis.pipeline import prepare_ecosystem_artifacts
from tqdm import tqdm


DEFAULT_STICHTAG = "2025-12-31"
HARVEST_ROOT = Path(ACTIVE_ECOSYSTEM["harvest"])
PREPROCESS_ROOT = Path(ACTIVE_ECOSYSTEM["preprocess"])
ANALYSIS_ROOT = Path(ACTIVE_ECOSYSTEM["analysis"])
POSTPROCESS_ROOT = Path(ACTIVE_ECOSYSTEM["postprocess"])


def main():
    parser = argparse.ArgumentParser(description="Run the full ecosystem pipeline for a specific STICHTAG.")
    parser.add_argument(
        "--stichtag",
        default=DEFAULT_STICHTAG,
        help="Snapshot date in YYYY-MM-DD format.",
    )
    args = parser.parse_args()
    stichtag = args.stichtag

    date.fromisoformat(stichtag)

    stages = [
        "Install dependencies",
        "Download repository snapshot",
        "Extract preambles",
        "Process metadata and insights",
        "Build analysis and postprocess artifacts",
    ]
    run_started = time.monotonic()
    progress = tqdm(total=len(stages), desc="Pipeline run", unit="stage")

    # Setup the environment
    progress.set_postfix_str(stages[0])
    install_requirements()
    progress.update(1)

    input_directory = HARVEST_ROOT
    output_directory = PREPROCESS_ROOT / stichtag

    print(
        f"Preparing {ACTIVE_ECOSYSTEM['proposal_term_plural']} "
        f"for ecosystem '{ACTIVE_ECOSYSTEM['slug']}' and STICHTAG {stichtag}..."
    )

    progress.set_postfix_str(stages[1])
    download_ips(stichtag=stichtag, local_dir=input_directory)
    progress.update(1)

    # Process files and extract preamble
    progress.set_postfix_str(stages[2])
    process_files_and_save_json(
        input_directory,
        output_directory,
        file_prefix=ACTIVE_ECOSYSTEM["document_prefix"],
        id_field=ACTIVE_ECOSYSTEM["primary_id_field"],
    )
    progress.update(1)

    # Process the metadata and insights
    progress.set_postfix_str(stages[3])
    process_ip_files(
        output_directory,
        output_directory,
        input_directory,
        file_prefix=ACTIVE_ECOSYSTEM["document_prefix"],
        proposal_label=ACTIVE_ECOSYSTEM["proposal_acronym"],
        id_field=ACTIVE_ECOSYSTEM["primary_id_field"],
    )
    progress.update(1)

    # Build ecosystem artifacts for visualization consumers.
    progress.set_postfix_str(stages[4])
    prepare_ecosystem_artifacts(
        proposal_json_dir=output_directory,
        artifact_root=ANALYSIS_ROOT,
        postprocess_root=POSTPROCESS_ROOT,
        stichtag=stichtag,
        id_field=ACTIVE_ECOSYSTEM["primary_id_field"],
        proposal_label=ACTIVE_ECOSYSTEM["proposal_acronym"],
    )
    progress.update(1)

    progress.close()

    elapsed = time.monotonic() - run_started
    print(f"\nPipeline completed in {elapsed:.1f}s.")

if __name__ == "__main__":
    main()
