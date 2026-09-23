import os
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

    def test_snapshot_checkout_follows_default_branch_state_at_cutoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "repo"

            def git(*args, date=None, capture_output=True):
                env = os.environ.copy()
                if date:
                    env["GIT_AUTHOR_DATE"] = date
                    env["GIT_COMMITTER_DATE"] = date
                return subprocess.run(
                    ["git", "-C", str(target), *args],
                    check=True,
                    capture_output=capture_output,
                    text=True,
                    env=env,
                )

            subprocess.run(
                ["git", "init", "--initial-branch=master", str(target)],
                check=True,
                capture_output=True,
            )
            git("config", "user.name", "Test User")
            git("config", "user.email", "test@example.com")
            git("commit", "--allow-empty", "-m", "root", date="2026-06-01T12:00:00Z")
            root_commit = git("rev-parse", "HEAD", capture_output=True).stdout.strip()

            git("checkout", "-b", "included-change")
            git(
                "commit",
                "--allow-empty",
                "-m",
                "included before cutoff",
                date="2026-06-24T12:00:00Z",
            )
            git("checkout", "master")
            git(
                "commit",
                "--allow-empty",
                "-m",
                "main before merge",
                date="2026-06-27T12:00:00Z",
            )
            git(
                "merge",
                "--no-ff",
                "included-change",
                "-m",
                "merge included change",
                date="2026-06-28T12:00:00Z",
            )
            cutoff_commit = git("rev-parse", "HEAD", capture_output=True).stdout.strip()

            git("checkout", "-b", "merged-later", root_commit)
            git(
                "commit",
                "--allow-empty",
                "-m",
                "side-branch change",
                date="2026-06-29T12:00:00Z",
            )
            git("checkout", "master")
            git(
                "merge",
                "--no-ff",
                "merged-later",
                "-m",
                "merge after cutoff",
                date="2026-07-02T12:00:00Z",
            )
            git("update-ref", "refs/remotes/origin/master", "HEAD")
            git(
                "symbolic-ref",
                "refs/remotes/origin/HEAD",
                "refs/remotes/origin/master",
            )

            _checkout_snapshot(target, "2026-06-30")

            checked_out = git("rev-parse", "HEAD", capture_output=True).stdout.strip()
            self.assertEqual(checked_out, cutoff_commit)


if __name__ == "__main__":
    unittest.main()
