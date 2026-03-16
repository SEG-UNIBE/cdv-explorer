from install_dependencies import install_requirements
from download import download_bips
from preamble_extraction import process_files_and_save_json
from bip_processing import process_bip_files
from ecosystem_config import ACTIVE_ECOSYSTEM
from datetime import date
from pathlib import Path


STICHTAG = "2025-12-31"
CLONE_DIRECTORY = Path(ACTIVE_ECOSYSTEM["clone_directory"])
JSON_ROOT = Path(ACTIVE_ECOSYSTEM["json_directory"])


def main():
    date.fromisoformat(STICHTAG)

    # Setup the environment
    install_requirements()

    input_directory = CLONE_DIRECTORY
    output_directory = JSON_ROOT / STICHTAG

    print(
        f"Preparing {ACTIVE_ECOSYSTEM['proposal_term_plural']} "
        f"for ecosystem '{ACTIVE_ECOSYSTEM['slug']}' and STICHTAG {STICHTAG}..."
    )
    download_bips(stichtag=STICHTAG, local_dir=input_directory)

    # Process files and extract preamble
    print("Starting preamble extraction...")
    process_files_and_save_json(
        input_directory,
        output_directory,
        file_prefix=ACTIVE_ECOSYSTEM["document_prefix"],
        id_field=ACTIVE_ECOSYSTEM["primary_id_field"],
    )

    # Process the metadata and insights
    process_bip_files(
        output_directory,
        output_directory,
        input_directory,
        file_prefix=ACTIVE_ECOSYSTEM["document_prefix"],
        proposal_label=ACTIVE_ECOSYSTEM["proposal_acronym"],
        id_field=ACTIVE_ECOSYSTEM["primary_id_field"],
    )

if __name__ == "__main__":
    main()
