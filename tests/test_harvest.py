import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.harvest.github_repo import _clone_or_update


class CloneOrUpdateTests(unittest.TestCase):
    def test_existing_empty_directory_is_used_as_clone_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "repo"
            target.mkdir()

            with patch("pipeline.harvest.github_repo.subprocess.run") as run:
                _clone_or_update("https://example.invalid/repo.git", target)

        run.assert_called_once_with(
            ["git", "clone", "https://example.invalid/repo.git", str(target)],
            check=True,
        )

    def test_existing_non_git_directory_still_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "repo"
            target.mkdir()
            (target / "README.md").write_text("not a git repo", encoding="utf-8")

            with self.assertRaises(ValueError):
                _clone_or_update("https://example.invalid/repo.git", target)


if __name__ == "__main__":
    unittest.main()
