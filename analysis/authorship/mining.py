import subprocess
from pathlib import Path
from typing import Any

from analysis.proposal_schema import normalize_proposal_document
from analysis.utils import parse_date_ymd as _parse_date_ymd

_GIT_BOTS = {"github-actions[bot]", "dependabot[bot]", "web-flow", "GitHub"}


def get_git_history(repo_dir: Path, file_path: Path) -> list[tuple[str, str, str]]:
    """Retrieve commit history for a file using local Git."""
    try:
        relative_file_path = file_path.relative_to(repo_dir)
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_dir),
                "log",
                "--pretty=format:%H|%ad|%an",
                "--",
                str(relative_file_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        commits = [
            line.split("|") for line in result.stdout.strip().split("\n") if line
        ]
        return [(commit[0], commit[1], commit[2]) for commit in commits]
    except subprocess.CalledProcessError:
        return []


def get_git_authors_on_first_day(git_history: list) -> list[str]:
    """Unique non-bot committers who touched the file on its first calendar day."""
    history = list(git_history or [])
    first_day: str | None = None

    for entry in reversed(history):
        if len(entry) >= 2:
            first_day = _parse_date_ymd(entry[1])
            if first_day:
                break

    if not first_day:
        return []

    seen: set = set()
    authors: list[str] = []
    for entry in history:
        if len(entry) < 3:
            continue
        author = entry[2]
        if not author or author in _GIT_BOTS:
            continue
        if _parse_date_ymd(entry[1]) != first_day:
            continue
        if author not in seen:
            seen.add(author)
            authors.append(author)
    return authors


def _insert_after(d: dict[str, Any], after_key: str, key: str, value: Any) -> None:
    """Insert key into dict immediately after after_key (in-place, no-op if key exists)."""
    if key in d:
        return
    items = list(d.items())
    d.clear()
    inserted = False
    for k, v in items:
        d[k] = v
        if k == after_key and not inserted:
            d[key] = value
            inserted = True
    if not inserted:
        d[key] = value


def update_metadata_from_git(
    json_data: dict[str, Any],
    proposal_file_path: Path,
    repo_dir: Path,
) -> dict[str, Any]:
    """Populate metadata from Git history in-place and return payload."""
    json_data = normalize_proposal_document(json_data)

    commit_info = get_git_history(repo_dir, proposal_file_path)
    last_commit_date = commit_info[0][1] if commit_info else None

    json_data["meta"].update(
        {
            "last_commit": last_commit_date,
            "total_commits": len(commit_info),
            "git_history": commit_info,
        }
    )

    preamble: dict[str, Any] = json_data.get("raw", {}).get("preamble", {})

    # Backfill author from committers present on the file's first day (e.g. NIPs)
    if not preamble.get("author") and commit_info:
        authors = get_git_authors_on_first_day(commit_info)
        if authors:
            _insert_after(preamble, after_key="title", key="author", value=authors)

    # Backfill created date from oldest commit when the preamble has none
    if not preamble.get("created") and commit_info:
        ymd = _parse_date_ymd(commit_info[-1][1])  # history is newest-first
        if ymd:
            _insert_after(preamble, after_key="author", key="created", value=ymd)

    return json_data
