"""Preamble extractor for Nostr NIPs using backtick-tagged metadata lines."""
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional

from tqdm import tqdm

from analysis.conformity.compliance import (
    add_missing_optional_fields as _add_missing_optional,
    build_compliance_payload,
    check_required_fields as _check_required,
)
from pipeline.preprocess.checkers import get_checker
from analysis.classification.preprocess import normalize_classification_fields
from analysis.proposal_schema import normalize_proposal_document

# Matches a line that consists entirely of backtick-wrapped tokens: `draft` `mandatory` `relay`
_TAG_LINE_PATTERN = re.compile(r"^(\s*`[^`]+`)+\s*$")
_BACKTICK_TOKENS = re.compile(r"`([^`]+)`")
_STATUS_LINE_PATTERN = re.compile(r"^\s*\*\*Status:\*\*\s*(.+?)\s*$", re.IGNORECASE)


def _parse_nip_file(content: str, filename: str, src_config: dict) -> Dict[str, Any]:
    """
    Parse NIP setext-heading format:

        NIP-01
        ======

        Basic protocol flow description
        --------------------------------

        `draft` `mandatory`
    """
    lines = content.splitlines()
    title: str | None = None
    tag_tokens: List[str] = []

    h1_found = False
    i = 0
    while i < len(lines):
        line = lines[i]
        next_line = lines[i + 1] if i + 1 < len(lines) else ""

        # Setext H1 (===) — the NIP identifier heading; skip it
        if not h1_found and re.match(r"^=+$", next_line.strip()) and next_line.strip():
            h1_found = True
            i += 2
            continue

        # ATX H1 fallback: "# NIP-XX"
        if not h1_found and re.match(r"^#\s+NIP-", line):
            h1_found = True
            i += 1
            continue

        if not h1_found:
            i += 1
            continue

        # Skip blank lines after H1
        if not line.strip():
            i += 1
            continue

        # Setext H2 (---) = the title
        if title is None and re.match(r"^-{2,}$", next_line.strip()):
            title = line.strip()
            i += 2
            continue

        # ATX H2 fallback: "## <title>"
        if title is None and re.match(r"^##\s+", line):
            title = re.sub(r"^##\s+", "", line).strip()
            i += 1
            continue

        if title is not None:
            # The first non-blank, non-heading line after the title is the tag line
            stripped = line.strip()
            if stripped:
                if _TAG_LINE_PATTERN.match(stripped):
                    tag_tokens = _BACKTICK_TOKENS.findall(stripped)
                else:
                    status_match = _STATUS_LINE_PATTERN.match(stripped)
                    if status_match:
                        tag_tokens = [status_match.group(1).strip()]
                break

        i += 1

    # Derive NIP id from filename stem (e.g. "01", "5A")
    nip_id = Path(filename).stem.upper()

    # Map tags to classification dimensions using aliases from config
    dims = src_config.get("classification", {}).get("dimensions", {})
    status_aliases: dict = {k.lower(): v for k, v in dims.get("status", {}).get("aliases", {}).items()}
    type_aliases: dict = {k.lower(): v for k, v in dims.get("type", {}).get("aliases", {}).items()}
    layer_aliases: dict = {k.lower(): v for k, v in dims.get("layer", {}).get("aliases", {}).items()}

    status: str | None = None
    proposal_type: str | None = None
    layer: str | None = None
    kind_parts: List[str] = []

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

    preamble: Dict[str, Any] = {
        "nip": nip_id,
        "title": title or "",
        "status": status or "Unknown",
    }
    if proposal_type is not None:
        preamble["type"] = proposal_type
    if layer is not None:
        preamble["layer"] = layer
    if kind_parts:
        preamble["kind"] = ", ".join(kind_parts)

    return preamble


def _save_json(
    preamble: Dict[str, Any],
    output_dir: Path,
    file_prefix: str,
    id_field: str,
    required_fields: List[str],
    optional_fields: List[str],
    compliance_payload: Optional[Dict[str, Any]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    nip_id = str(preamble.get(id_field, "unknown")).upper()
    json_filename = f"{file_prefix}-{nip_id}.json"
    output_path = output_dir / json_filename

    existing: Dict[str, Any] = {}
    if output_path.exists():
        try:
            existing = normalize_proposal_document(json.loads(output_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            existing = {}

    ordered_preamble = OrderedDict()
    for field in required_fields + optional_fields:
        ordered_preamble[field] = preamble.get(field)

    json_data = normalize_proposal_document(existing)
    json_data["raw"]["preamble"] = ordered_preamble
    json_data["insights"]["formal_compliance"] = compliance_payload or {}

    for key, value in existing.items():
        if key not in json_data:
            json_data[key] = value

    output_path.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")


def extract(
    src_config: dict,
    harvest_dir: Path,
    output_dir: Path,
    progress_callback=None,
) -> None:
    """Extract NIP metadata from backtick-tag lines and write per-NIP JSON."""
    preamble_config = src_config["preamble"]
    required_fields: List[str] = preamble_config["required_fields"]
    optional_fields: List[str] = preamble_config["optional_fields"]
    file_prefix: str = src_config["document_prefix"]
    id_field: str = src_config["primary_id_field"]

    file_pattern = re.compile(src_config["document_file_pattern"], re.IGNORECASE)
    proposal_files = sorted(
        p for p in harvest_dir.iterdir()
        if file_pattern.match(p.name)
    )

    live = sys.stdout.isatty()
    local_progress = progress_callback is None and live
    progress = tqdm(
        proposal_files,
        desc="NIP tag extraction",
        unit="ip",
        leave=False,
        position=1,
        dynamic_ncols=local_progress,
        file=sys.stdout,
        disable=not local_progress,
        mininterval=0.5,
    )

    for proposal_file in progress:
        if local_progress:
            progress.set_postfix_str(proposal_file.name, refresh=False)
        if progress_callback is not None:
            progress_callback(proposal_file.name, 0)

        content = proposal_file.read_text(encoding="utf-8")
        preamble = _parse_nip_file(content, proposal_file.name, src_config)
        preamble = normalize_classification_fields(preamble)
        _check_required(preamble, required_fields)
        _add_missing_optional(preamble, optional_fields)
        checker = get_checker(src_config.get("compliance_checker", "nip"))
        compliance_payload = build_compliance_payload(checker(preamble, content, src_config))
        preamble["Compliance Score"] = compliance_payload["score"]
        _save_json(
            preamble, output_dir, file_prefix, id_field,
            required_fields, optional_fields, compliance_payload,
        )

        if progress_callback is not None:
            progress_callback(proposal_file.name, 1)

    progress.close()
