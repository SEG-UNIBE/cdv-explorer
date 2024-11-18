import subprocess
import sys


def install_requirements(requirements_file='requirements.txt'):
    """
    Installs required libraries listed in the requirements.txt file.
    """
    try:
        print("Upgrading pip...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])

        print(f"Installing requirements from {requirements_file}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_file])

        print("All required libraries have been installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error occurred during installation: {e}")
        sys.exit(1)
