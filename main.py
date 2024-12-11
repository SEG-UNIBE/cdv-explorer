from install_dependencies import install_requirements
from download import download_bips
from preamble_extraction import process_files_and_save_json
from bip_processing import process_bip_files, load_github_token
import os


def main():

    # Setup the environment
    install_requirements()

    # Check if the BIP download directory exists
    input_directory = 'bips_downloaded'
    output_directory = 'bips_json'

    if not os.path.exists(input_directory):
        print("BIP directory not found. Downloading BIPs...")
        download_bips()
    else:
        print("BIP directory already exists. Skipping download step.")

    # Process files and extract preamble
    print("Starting preamble extraction...")
    process_files_and_save_json(input_directory, output_directory)


    # Process the metadata and insigths
    github_token = load_github_token('github_token.txt')
    process_bip_files(output_directory, output_directory, github_token)

if __name__ == "__main__":
    main()
