from typing import Any, Dict

from ecosystem_config import ACTIVE_ECOSYSTEM


CLASSIFICATION_CONFIG = ACTIVE_ECOSYSTEM.get("classification", {})
LAYER_ALIASES = CLASSIFICATION_CONFIG.get("layer_aliases", {})
STATUS_ALIASES = CLASSIFICATION_CONFIG.get("status_aliases", {})
TYPE_ALIASES = CLASSIFICATION_CONFIG.get("type_aliases", {})


def normalize_classification_fields(
    preamble: Dict[str, Any],
    layer_aliases: Dict[str, str] | None = None,
    status_aliases: Dict[str, str] | None = None,
    type_aliases: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    normalized = dict(preamble)
    active_layer_aliases = layer_aliases if layer_aliases is not None else LAYER_ALIASES
    active_status_aliases = status_aliases if status_aliases is not None else STATUS_ALIASES
    active_type_aliases = type_aliases if type_aliases is not None else TYPE_ALIASES

    if normalized.get("layer") is not None:
        normalized["layer"] = active_layer_aliases.get(normalized["layer"], normalized["layer"])
    if normalized.get("status") is not None:
        normalized["status"] = active_status_aliases.get(normalized["status"], normalized["status"])
    if normalized.get("type") is not None:
        normalized["type"] = active_type_aliases.get(normalized["type"], normalized["type"])

    return normalized

