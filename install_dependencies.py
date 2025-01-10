import subprocess
import sys

def install_requirements(requirements_file='requirements.txt'):
    """
    Installs required libraries listed in the requirements.txt file,
    but only upgrades/install if needed (won't reinstall if they're already correct).
    """
    try:
        print("Upgrading pip (optional step)...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])

        print(f"Installing/Upgrading requirements from {requirements_file} only if needed...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "--upgrade",
            "--upgrade-strategy", "only-if-needed",
            "-r", requirements_file
        ])

        print("All required libraries have been installed or were already up-to-date.")
    except subprocess.CalledProcessError as e:
        print(f"Error occurred during installation: {e}")
        sys.exit(1)
