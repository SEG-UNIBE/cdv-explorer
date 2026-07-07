import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

from analysis.classification.preprocess import normalize_classification_fields
from pipeline.source_context import SourceContext

PRE_BLOCK_PATTERN = re.compile(r"<pre>(.*?)</pre>", re.DOTALL | re.IGNORECASE)
FENCED_BLOCK_PATTERN = re.compile(r"^\s*```[^\n]*\n(.*?)\n```\s*(?:\n|$)", re.DOTALL)
PRE_BLOCK_LINE_PATTERN = re.compile(r"^\s{0,2}(\w+(?:-\w+)*):\s*(.*)")
RFC822_HEADER_PATTERN = re.compile(r"^\s*([A-Za-z][A-Za-z0-9-]*):\s*(.*)$")
NIP_TAG_LINE_PATTERN = re.compile(r"^(\s*`[^`]+`)+\s*$")
NIP_BACKTICK_TOKENS = re.compile(r"`([^`]+)`")
NIP_STATUS_LINE_PATTERN = re.compile(r"^\s*\*\*Status:\*\*\s*(.+?)\s*$", re.IGNORECASE)
PLACEHOLDER_PATH_PATTERN = re.compile(r"-(?:x{3,}|\?{3,})(?:[-.]|$)", re.IGNORECASE)
PATH_NUMERIC_ID_PATTERN = re.compile(r"(\d+)")


def _format_value(key: str, value: str, source_context: SourceContext) -> Any:
    if key in source_context.list_valued_fields:
        return [line.strip() for line in value.split("\n") if line.strip()]
    return value.strip()


def _extract_raw_pre_block(file_content: str) -> str:
    pre_block_match = PRE_BLOCK_PATTERN.search(file_content)
    if pre_block_match:
        return pre_block_match.group(1)

    fenced_block_match = FENCED_BLOCK_PATTERN.search(file_content)
    if fenced_block_match:
        return fenced_block_match.group(1)

    return ""


def _parse_pre_block_preamble(
    file_content: str, source_context: SourceContext
) -> dict[str, Any]:
    pre_block = _extract_raw_pre_block(file_content)
    if not pre_block:
        return {}

    preamble: dict[str, Any] = {}
    current_key = None
    current_value = ""

    for line in pre_block.splitlines():
        match = PRE_BLOCK_LINE_PATTERN.match(line)
        if match:
            if current_key:
                preamble[current_key] = _format_value(
                    current_key, current_value, source_context
                )
            current_key = match.group(1).strip().lower().replace("-", "_")
            current_value = match.group(2).strip()
            continue

        if current_key and (line.startswith(" " * 4) or line.startswith("\t")):
            current_value += "\n" + line.strip()

    if current_key:
        preamble[current_key] = _format_value(
            current_key, current_value, source_context
        )

    return preamble


def _extract_top_rfc822_block(file_content: str) -> str | None:
    content = file_content.lstrip("\ufeff")
    lines = content.splitlines()
    block_lines: list[str] = []
    started = False

    for line in lines:
        if not started and not line.strip():
            continue

        if not started:
            if RFC822_HEADER_PATTERN.match(line):
                started = True
                block_lines.append(line)
            else:
                return None
            continue

        if not line.strip():
            break

        if RFC822_HEADER_PATTERN.match(line) or re.match(r"^\s+\S", line):
            block_lines.append(line)
            continue

        break

    return "\n".join(block_lines) if block_lines else None


def _parse_rfc822_preamble(file_content: str) -> dict[str, Any]:
    block = _extract_top_rfc822_block(file_content)
    if not block:
        return {}

    preamble: dict[str, Any] = {}
    current_key = None
    current_value_lines: list[str] = []

    for raw_line in block.splitlines():
        if not raw_line.strip():
            continue

        match = RFC822_HEADER_PATTERN.match(raw_line)
        if match:
            if current_key is not None:
                preamble[current_key] = "\n".join(current_value_lines).strip()
            current_key = match.group(1).strip().lower().replace("-", "_")
            current_value_lines = [match.group(2).strip()]
            continue

        if current_key is not None and re.match(r"^\s+\S", raw_line):
            current_value_lines.append(raw_line.strip())

    if current_key is not None:
        preamble[current_key] = "\n".join(current_value_lines).strip()

    return preamble


def _parse_nip_tag_preamble(
    file_content: str,
    source_context: SourceContext,
    *,
    fallback_path: str | None = None,
) -> dict[str, Any]:
    if source_context.preprocessor != "nip_tags":
        return {}

    lines = file_content.splitlines()
    title: str | None = None
    tag_tokens: list[str] = []

    h1_found = False
    index = 0
    while index < len(lines):
        line = lines[index]
        next_line = lines[index + 1] if index + 1 < len(lines) else ""

        if not h1_found and re.match(r"^=+$", next_line.strip()) and next_line.strip():
            h1_found = True
            index += 2
            continue

        if not h1_found and re.match(r"^#\s+NIP-", line):
            h1_found = True
            index += 1
            continue

        if not h1_found:
            index += 1
            continue

        if not line.strip():
            index += 1
            continue

        if title is None and re.match(r"^-{2,}$", next_line.strip()):
            title = line.strip()
            index += 2
            continue

        if title is None and re.match(r"^##\s+", line):
            title = re.sub(r"^##\s+", "", line).strip()
            index += 1
            continue

        if title is not None:
            stripped = line.strip()
            if stripped:
                if NIP_TAG_LINE_PATTERN.match(stripped):
                    tag_tokens = NIP_BACKTICK_TOKENS.findall(stripped)
                else:
                    status_match = NIP_STATUS_LINE_PATTERN.match(stripped)
                    if status_match:
                        tag_tokens = [status_match.group(1).strip()]
                break

        index += 1

    dims = source_context.classification_dimensions
    status_aliases = {
        k.lower(): v for k, v in (dims.get("status", {}).get("aliases") or {}).items()
    }
    type_aliases = {
        k.lower(): v for k, v in (dims.get("type", {}).get("aliases") or {}).items()
    }
    layer_aliases = {
        k.lower(): v for k, v in (dims.get("layer", {}).get("aliases") or {}).items()
    }

    status: str | None = None
    proposal_type: str | None = None
    layer: str | None = None
    kind_parts: list[str] = []

    for token in tag_tokens:
        lower = token.lower()
        if lower in status_aliases and status is None:
            status = status_aliases[lower]
        elif lower in type_aliases and proposal_type is None:
            proposal_type = type_aliases[lower]
        elif lower in layer_aliases and layer is None:
            layer = layer_aliases[lower]
        else:
            kind_parts.append(token)

    proposal_id = ""
    if fallback_path:
        proposal_id = Path(fallback_path).stem
        document_prefix = source_context.document_prefix
        if document_prefix and proposal_id.lower().startswith(
            f"{document_prefix.lower()}-"
        ):
            proposal_id = proposal_id[len(document_prefix) + 1 :]
        proposal_id = proposal_id.upper()

    preamble: dict[str, Any] = {}
    if proposal_id:
        preamble[source_context.primary_id_field or "id"] = proposal_id
    if title:
        preamble["title"] = title
    if status:
        preamble["status"] = status
    if proposal_type:
        preamble["type"] = proposal_type
    if layer:
        preamble["layer"] = layer
    if kind_parts:
        preamble["kind"] = ", ".join(kind_parts)

    return preamble


def _normalize_preamble(
    preamble: dict[str, Any], source_context: SourceContext
) -> dict[str, Any]:
    normalized = dict(preamble)

    for source_key, canonical_key in source_context.field_aliases.items():
        if canonical_key in normalized or source_key not in normalized:
            continue
        normalized[canonical_key] = normalized[source_key]

    return normalize_classification_fields(normalized, source_context=source_context)


def _extract_snapshot_preamble(
    file_content: str,
    source_context: SourceContext,
    *,
    fallback_path: str | None = None,
) -> dict[str, Any]:
    pre_block_preamble = _parse_pre_block_preamble(file_content, source_context)
    if pre_block_preamble:
        return _normalize_preamble(pre_block_preamble, source_context)

    rfc822_preamble = _parse_rfc822_preamble(file_content)
    if rfc822_preamble:
        return _normalize_preamble(rfc822_preamble, source_context)

    nip_tag_preamble = _parse_nip_tag_preamble(
        file_content, source_context, fallback_path=fallback_path
    )
    if nip_tag_preamble:
        return _normalize_preamble(nip_tag_preamble, source_context)

    return {}


def _extract_status_snapshot(
    file_content: str,
    source_context: SourceContext | None = None,
) -> str | None:
    normalized = _extract_snapshot_preamble(
        file_content, source_context or SourceContext.default()
    )
    status = str(normalized.get("status") or "").strip()
    if status:
        return status

    return None


def _normalize_identity_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    return re.sub(r"\s+", " ", text)


def _normalize_title(value: Any) -> str:
    text = _normalize_identity_text(value)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _normalize_proposal_id(value: Any) -> str:
    text = _normalize_identity_text(value)
    if not text:
        return ""
    if re.fullmatch(r"x+", text):
        return ""
    if text.isdigit():
        return str(int(text))
    if re.fullmatch(r"[0-9a-z]+", text):
        return text
    return ""


def _normalize_authors(value: Any) -> set[str]:
    if isinstance(value, list):
        raw_values = value
    elif value is None:
        raw_values = []
    else:
        raw_values = str(value).split("\n")

    return {
        _normalize_identity_text(item)
        for item in raw_values
        if _normalize_identity_text(item)
    }


def _extract_path_proposal_id(file_path: Path, source_context: SourceContext) -> str:
    if _is_placeholder_path(str(file_path)):
        return ""

    stem = file_path.stem.strip()
    document_prefix = source_context.document_prefix
    if document_prefix and stem.lower().startswith(f"{document_prefix.lower()}-"):
        stem = stem[len(document_prefix) + 1 :]

    normalized = _normalize_proposal_id(stem)
    if normalized:
        return normalized

    match = PATH_NUMERIC_ID_PATTERN.search(file_path.stem)
    if not match:
        return ""
    return str(int(match.group(1)))


def _build_snapshot_identity(
    preamble: dict[str, Any],
    source_context: SourceContext,
    *,
    fallback_path: str | None = None,
) -> dict[str, Any]:
    primary_id_field = source_context.primary_id_field
    raw_proposal_id = preamble.get(primary_id_field)
    has_declared_proposal_id = (
        bool(primary_id_field)
        and primary_id_field in preamble
        and bool(_normalize_identity_text(raw_proposal_id))
    )
    proposal_id = _normalize_proposal_id(raw_proposal_id)
    if not proposal_id and not has_declared_proposal_id and fallback_path:
        proposal_id = _extract_path_proposal_id(Path(fallback_path), source_context)

    created = _normalize_identity_text(preamble.get("created"))[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", created):
        created = ""

    return {
        "proposal_id": proposal_id,
        "title": _normalize_title(preamble.get("title")),
        "created": created,
        "authors": _normalize_authors(preamble.get("author")),
    }


def _is_placeholder_path(path: str) -> bool:
    return bool(PLACEHOLDER_PATH_PATTERN.search(Path(path).name))


def _is_same_proposal_snapshot(
    candidate_identity: dict[str, Any],
    target_identity: dict[str, Any],
    *,
    candidate_path: str,
) -> bool:
    target_id = str(target_identity.get("proposal_id") or "").strip()
    candidate_id = str(candidate_identity.get("proposal_id") or "").strip()

    if target_id and candidate_id:
        return target_id == candidate_id
    if target_id and not _is_placeholder_path(candidate_path):
        return True
    if not _is_placeholder_path(candidate_path):
        return True

    created_matches = (
        bool(target_identity.get("created"))
        and bool(candidate_identity.get("created"))
        and target_identity["created"] == candidate_identity["created"]
    )
    title_matches = (
        bool(target_identity.get("title"))
        and bool(candidate_identity.get("title"))
        and target_identity["title"] == candidate_identity["title"]
    )
    author_matches = bool(
        set(target_identity.get("authors") or set())
        & set(candidate_identity.get("authors") or set())
    )

    if created_matches and (title_matches or author_matches):
        return True
    if title_matches and author_matches:
        return True

    return False


def _parse_snapshot_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _resolve_reporting_standard(
    event_date_text: str, source_context: SourceContext
) -> str:
    event_date = _parse_snapshot_date(event_date_text[:10])
    regimes = source_context.classification_config.get("regimes", [])
    last_seen = ""

    for entry in regimes:
        if not isinstance(entry, dict):
            continue

        standard = str(entry.get("standard") or "").strip()
        if not standard:
            continue
        last_seen = standard

        start_date = _parse_snapshot_date(entry.get("valid_from"))
        end_date = _parse_snapshot_date(entry.get("valid_until"))

        if event_date is None:
            continue
        if start_date is not None and event_date < start_date:
            continue
        if end_date is not None and event_date > end_date:
            continue

        return standard

    return last_seen


def _parse_git_history_with_paths(stdout: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    for raw_line in stdout.splitlines():
        line = raw_line.rstrip("\n")
        if line.startswith("__COMMIT__"):
            if current and current.get("path"):
                entries.append(current)
            commit, timestamp, author = line[len("__COMMIT__") :].split("|", 2)
            current = {
                "commit": commit,
                "timestamp": timestamp,
                "author": author,
                "path": "",
            }
            continue

        if not current or not line.strip():
            continue

        current["path"] = line.split("\t")[-1].strip()

    if current and current.get("path"):
        entries.append(current)

    return entries


def extract_status_timeline(
    repo_dir: Path,
    file_path: Path,
    source_context: SourceContext | None = None,
) -> list[dict[str, str]]:
    context = source_context or SourceContext.default()
    try:
        relative_file_path = file_path.relative_to(repo_dir)
    except ValueError:
        return []

    try:
        target_content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    target_preamble = _extract_snapshot_preamble(
        target_content,
        context,
        fallback_path=str(relative_file_path),
    )
    target_identity = _build_snapshot_identity(
        target_preamble,
        context,
        fallback_path=str(relative_file_path),
    )

    try:
        log_result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_dir),
                "log",
                "--follow",
                "--format=__COMMIT__%H|%cI|%an",
                "--name-status",
                "--",
                str(relative_file_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
    except subprocess.CalledProcessError:
        return []

    history_entries = list(reversed(_parse_git_history_with_paths(log_result.stdout)))
    timeline: list[dict[str, str]] = []
    previous_snapshot = None

    for entry in history_entries:
        try:
            content_result = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_dir),
                    "show",
                    f"{entry['commit']}:{entry['path']}",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=True,
            )
        except subprocess.CalledProcessError:
            continue

        snapshot_preamble = _extract_snapshot_preamble(
            content_result.stdout,
            context,
            fallback_path=entry["path"],
        )
        snapshot_identity = _build_snapshot_identity(
            snapshot_preamble,
            context,
            fallback_path=entry["path"],
        )
        if not _is_same_proposal_snapshot(
            snapshot_identity,
            target_identity,
            candidate_path=entry["path"],
        ):
            continue

        status = str(snapshot_preamble.get("status") or "").strip()
        if not status:
            continue

        standard = _resolve_reporting_standard(entry["timestamp"], context)
        snapshot = (status, standard)
        if snapshot == previous_snapshot:
            continue

        timeline.append(
            {
                "commit": entry["commit"],
                "timestamp": entry["timestamp"],
                "date": entry["timestamp"][:10],
                "author": entry["author"],
                "path": entry["path"],
                "status": status,
                "standard": standard,
            }
        )
        previous_snapshot = snapshot

    return timeline
