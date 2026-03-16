from ecosystems import ECOSYSTEM_REGISTRY


ACTIVE_ECOSYSTEM_SLUG = "bitcoin"


def _load_active_ecosystem() -> dict:
    slug = ACTIVE_ECOSYSTEM_SLUG
    ecosystem = ECOSYSTEM_REGISTRY.get(slug)
    if ecosystem is None:
        available = ", ".join(sorted(ECOSYSTEM_REGISTRY.keys()))
        raise ValueError(f"Unknown ecosystem slug '{slug}'. Available: {available}")
    return ecosystem


ACTIVE_ECOSYSTEM = _load_active_ecosystem()
