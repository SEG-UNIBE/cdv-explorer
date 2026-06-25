from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

from ecosystems import ECOSYSTEM_REGISTRY


@dataclass(frozen=True)
class SourceContext:
    """Runtime source configuration passed explicitly through pipeline stages."""

    config: Mapping[str, Any]
    ecosystem_slug: str | None = None
    source_slug: str | None = None

    @classmethod
    def from_config(
        cls,
        config: Mapping[str, Any],
        *,
        ecosystem_slug: str | None = None,
        source_slug: str | None = None,
    ) -> "SourceContext":
        return cls(config=config, ecosystem_slug=ecosystem_slug, source_slug=source_slug)

    @classmethod
    def default(cls) -> "SourceContext":
        eco_slug = os.environ.get("CDV_ECOSYSTEM") or next(iter(ECOSYSTEM_REGISTRY), None)
        if not eco_slug:
            raise ValueError("No ecosystems registered. Add a .yml file to the ecosystems/ directory.")
        eco = ECOSYSTEM_REGISTRY.get(eco_slug)
        if eco is None:
            available = ", ".join(sorted(ECOSYSTEM_REGISTRY.keys()))
            raise ValueError(f"Unknown ecosystem '{eco_slug}'. Available: {available}")

        sources: Mapping[str, Mapping[str, Any]] = eco.get("sources", {})
        if not sources:
            raise ValueError(f"Ecosystem '{eco_slug}' defines no sources.")

        src_slug = os.environ.get("CDV_SOURCE") or next(iter(sources))
        source = sources.get(src_slug)
        if source is None:
            available = ", ".join(sorted(sources.keys()))
            raise ValueError(f"Unknown source '{src_slug}' in ecosystem '{eco_slug}'. Available: {available}")

        return cls.from_config(source, ecosystem_slug=eco_slug, source_slug=src_slug)

    @property
    def preamble_config(self) -> Mapping[str, Any]:
        return self.config.get("preamble", {})

    @property
    def field_aliases(self) -> Mapping[str, str]:
        return self.preamble_config.get("field_aliases", {})

    @property
    def list_valued_fields(self) -> set[str]:
        return set(self.preamble_config.get("list_valued_fields", []))

    @property
    def preamble_interrelation_types(self) -> tuple[str, ...]:
        if "interrelation_types" in self.preamble_config:
            fields = self.preamble_config.get("interrelation_types") or []
            return tuple(str(field) for field in fields if str(field).strip())
        if "dependency_fields" in self.preamble_config:
            fields = self.preamble_config.get("dependency_fields") or []
            return tuple(str(field) for field in fields if str(field).strip())
        return ("requires", "replaces", "proposed_replacement")

    @property
    def preamble_dependency_fields(self) -> tuple[str, ...]:
        return self.preamble_interrelation_types

    @property
    def classification_config(self) -> Mapping[str, Any]:
        return self.config.get("classification", {})

    @property
    def classification_dimensions(self) -> Mapping[str, Mapping[str, Any]]:
        return self.classification_config.get("dimensions", {})

    @property
    def classification_fields(self) -> list[str]:
        return list(self.classification_dimensions.keys())

    def classification_aliases(self, field: str) -> Mapping[str, str]:
        return self.classification_dimensions.get(field, {}).get("aliases", {})

    @property
    def ecosystem_source_configs(self) -> Mapping[str, Mapping[str, Any]]:
        if self.ecosystem_slug:
            ecosystem = ECOSYSTEM_REGISTRY.get(self.ecosystem_slug)
            sources = ecosystem.get("sources", {}) if isinstance(ecosystem, Mapping) else {}
            if sources:
                return sources
        if self.source_slug:
            return {self.source_slug: self.config}
        return {}

    @property
    def ecosystem_config(self) -> Mapping[str, Any]:
        if not self.ecosystem_slug:
            return {}
        ecosystem = ECOSYSTEM_REGISTRY.get(self.ecosystem_slug)
        return ecosystem if isinstance(ecosystem, Mapping) else {}

    @property
    def llm_config(self) -> Mapping[str, Any]:
        config = self.ecosystem_config.get("llm", {})
        return config if isinstance(config, Mapping) else {}

    @property
    def llm_model(self) -> str | None:
        model = self.llm_config.get("model")
        if model is None:
            return None
        value = str(model).strip()
        return value or None

    @property
    def llm_reasoning(self) -> Mapping[str, Any] | None:
        if "reasoning_effort" not in self.llm_config:
            return None
        effort = self.llm_config.get("reasoning_effort")
        return {"effort": str(effort)} if effort is not None else {}

    @property
    def primary_id_field(self) -> str:
        return str(self.config.get("primary_id_field") or "").strip()

    @property
    def document_prefix(self) -> str:
        return str(self.config.get("document_prefix") or "").strip()

    @property
    def preprocessor(self) -> str:
        return str(self.config.get("preprocessor") or "").strip()

    @property
    def proposal_label(self) -> str:
        return str(self.config.get("proposal_acronym") or "IP").strip() or "IP"

    @property
    def proposal_singular(self) -> str:
        return str(self.config.get("proposal_term_singular") or "proposal").strip() or "proposal"

    @property
    def reference_pattern(self) -> str:
        return str(self.config.get("reference_pattern") or "").strip()

    @property
    def max_proposal_id(self) -> Any:
        return self.config.get("max_proposal_id")

    def normalize_classification_fields(self, preamble: Mapping[str, Any]) -> dict[str, Any]:
        normalized = dict(preamble)
        for field in ("layer", "status", "type"):
            if normalized.get(field) is not None:
                aliases = self.classification_aliases(field)
                normalized[field] = aliases.get(normalized[field], normalized[field])
        return normalized
