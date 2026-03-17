import subprocess
import sys


def _emit_progress(progress_callback=None, status_callback=None, message=None, advance=0):
    if progress_callback is not None:
        progress_callback(message, advance)
        return
    if status_callback is not None and message is not None:
        status_callback(message)


def install_requirements(requirements_file='requirements.txt', status_callback=None, progress_callback=None):
    """
    Installs required libraries listed in the requirements.txt file,
    but only upgrades/install if needed (won't reinstall if they're already correct).
    """
    try:
        _emit_progress(
            progress_callback=progress_callback,
            status_callback=status_callback,
            message="Upgrading pip",
        )
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])

        _emit_progress(
            progress_callback=progress_callback,
            status_callback=status_callback,
            message="Installing requirements",
            advance=1,
        )
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "--upgrade",
            "--upgrade-strategy", "only-if-needed",
            "-r", requirements_file
        ])
        _emit_progress(
            progress_callback=progress_callback,
            status_callback=status_callback,
            message="Completed",
            advance=1,
        )
    except subprocess.CalledProcessError as e:
        raise SystemExit(1) from e
