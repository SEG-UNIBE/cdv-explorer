import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.harvest.github_repo import _checkout_snapshot, _clone_or_update


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

    def test_existing_git_directory_can_continue_when_fetch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "repo"
            (target / ".git").mkdir(parents=True)
            messages = []

            with patch(
                "pipeline.harvest.github_repo.subprocess.run",
                side_effect=subprocess.CalledProcessError(128, ["git", "fetch"]),
            ) as run:
                _clone_or_update(
                    "https://example.invalid/repo.git",
                    target,
                    progress_callback=lambda message, _advance=0: messages.append(
                        message
                    ),
                )

        run.assert_called_once_with(
            ["git", "-C", str(target), "fetch", "--all", "--prune"],
            check=True,
        )
        self.assertIn("Fetch failed; using existing local repository", messages)

    def test_snapshot_checkout_forces_pipeline_managed_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "repo"
            target.mkdir()

            def fake_run(command, **kwargs):
                if "symbolic-ref" in command:
                    return subprocess.CompletedProcess(
                        command, 0, stdout="refs/remotes/origin/master\n"
                    )
                if "rev-list" in command:
                    return subprocess.CompletedProcess(command, 0, stdout="abc123\n")
                return subprocess.CompletedProcess(command, 0)

            with patch(
                "pipeline.harvest.github_repo.subprocess.run", side_effect=fake_run
            ) as run:
                _checkout_snapshot(target, "2026-05-28")

        run.assert_any_call(
            ["git", "-C", str(target), "checkout", "--force", "--detach", "abc123"],
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
