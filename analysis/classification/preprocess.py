from typing import Any

from pipeline.source_context import SourceContext


def normalize_classification_fields(
    preamble: dict[str, Any],
    layer_aliases: dict[str, str] | None = None,
    status_aliases: dict[str, str] | None = None,
    type_aliases: dict[str, str] | None = None,
    source_context: SourceContext | None = None,
) -> dict[str, Any]:
    normalized = dict(preamble)
    context = source_context or SourceContext.default()
    active_layer_aliases = (
        layer_aliases
        if layer_aliases is not None
        else context.classification_aliases("layer")
    )
    active_status_aliases = (
        status_aliases
        if status_aliases is not None
        else context.classification_aliases("status")
    )
    active_type_aliases = (
        type_aliases
        if type_aliases is not None
        else context.classification_aliases("type")
    )

    if normalized.get("layer") is not None:
        normalized["layer"] = active_layer_aliases.get(
            normalized["layer"], normalized["layer"]
        )
    if normalized.get("status") is not None:
        normalized["status"] = active_status_aliases.get(
            normalized["status"], normalized["status"]
        )
    if normalized.get("type") is not None:
        normalized["type"] = active_type_aliases.get(
            normalized["type"], normalized["type"]
        )

    return normalized
