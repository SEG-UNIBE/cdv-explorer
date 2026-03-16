from install_dependencies import install_requirements
from download import download_ips
from preamble_extraction import process_files_and_save_json
from ip_processing import process_ip_files
from ecosystem_config import ACTIVE_ECOSYSTEM
from datetime import date
import argparse
from pathlib import Path
from analysis.pipeline import prepare_ecosystem_artifacts


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

    # Setup the environment
    install_requirements()

    input_directory = HARVEST_ROOT
    output_directory = PREPROCESS_ROOT / stichtag

    print(
        f"Preparing {ACTIVE_ECOSYSTEM['proposal_term_plural']} "
        f"for ecosystem '{ACTIVE_ECOSYSTEM['slug']}' and STICHTAG {stichtag}..."
    )
    download_ips(stichtag=stichtag, local_dir=input_directory)

    # Process files and extract preamble
    print("Starting preamble extraction...")
    process_files_and_save_json(
        input_directory,
        output_directory,
        file_prefix=ACTIVE_ECOSYSTEM["document_prefix"],
        id_field=ACTIVE_ECOSYSTEM["primary_id_field"],
    )

    # Process the metadata and insights
    process_ip_files(
        output_directory,
        output_directory,
        input_directory,
        file_prefix=ACTIVE_ECOSYSTEM["document_prefix"],
        proposal_label=ACTIVE_ECOSYSTEM["proposal_acronym"],
        id_field=ACTIVE_ECOSYSTEM["primary_id_field"],
    )

    # Build ecosystem artifacts for visualization consumers.
    prepare_ecosystem_artifacts(
        proposal_json_dir=output_directory,
        artifact_root=ANALYSIS_ROOT,
        postprocess_root=POSTPROCESS_ROOT,
        stichtag=stichtag,
        id_field=ACTIVE_ECOSYSTEM["primary_id_field"],
        proposal_label=ACTIVE_ECOSYSTEM["proposal_acronym"],
    )

if __name__ == "__main__":
    main()
