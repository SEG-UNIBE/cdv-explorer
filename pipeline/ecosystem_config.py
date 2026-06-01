import os
from ecosystems import ECOSYSTEM_REGISTRY


def _load_active_source() -> dict:
    eco_slug = os.environ.get("CDV_ECOSYSTEM") or next(iter(ECOSYSTEM_REGISTRY), None)
    if not eco_slug:
        raise ValueError("No ecosystems registered. Add a .yml file to the ecosystems/ directory.")
    eco = ECOSYSTEM_REGISTRY.get(eco_slug)
    if eco is None:
        available = ", ".join(sorted(ECOSYSTEM_REGISTRY.keys()))
        raise ValueError(f"Unknown ecosystem '{eco_slug}'. Available: {available}")

    sources: dict = eco.get("sources", {})
    if not sources:
        raise ValueError(f"Ecosystem '{eco_slug}' defines no sources.")

    src_slug = os.environ.get("CDV_SOURCE") or next(iter(sources))
    source = sources.get(src_slug)
    if source is None:
        available = ", ".join(sorted(sources.keys()))
        raise ValueError(
            f"Unknown source '{src_slug}' in ecosystem '{eco_slug}'. Available: {available}"
        )

    return source


ACTIVE_ECOSYSTEM = _load_active_source()
