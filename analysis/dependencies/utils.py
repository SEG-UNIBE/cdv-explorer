import re
from typing import Any, Mapping


HEX_REFERENCE_CLASS_PATTERN = re.compile(r"\[[^\]]*0-9[^\]]*A-F[^\]]*a-f[^\]]*\]")


def uses_hex_proposal_ids(proposal_label: str = "IP", reference_pattern: str = "") -> bool:
    return proposal_label.upper() == "NIP" or bool(HEX_REFERENCE_CLASS_PATTERN.search(reference_pattern))


def normalize_reference_id(
    value: Any,
    *,
    proposal_label: str = "IP",
    reference_pattern: str = "",
    max_proposal_id: Any = None,
    max_reference_digits: int = 6,
) -> str | None:
    text = str(value).strip()
    if not text:
        return None

    if uses_hex_proposal_ids(proposal_label, reference_pattern):
        if not re.fullmatch(rf"[0-9A-Fa-f]{{1,{max_reference_digits}}}", text):
            return None
        number = int(text, 16)
        if max_proposal_id is not None and number > int(max_proposal_id):
            return None
        normalized = text.upper()
        return normalized.zfill(2) if len(normalized) == 1 else normalized

    try:
        number = int(text)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    if max_proposal_id is not None and number > int(max_proposal_id):
        return None
    return str(number)


def normalize_reference_id_for_config(
    value: Any,
    config: Mapping[str, Any],
    *,
    max_reference_digits: int = 6,
) -> str | None:
    return normalize_reference_id(
        value,
        proposal_label=str(config.get("proposal_label") or "IP"),
        reference_pattern=str(config.get("reference_pattern") or ""),
        max_proposal_id=config.get("max_proposal_id"),
        max_reference_digits=max_reference_digits,
    )
