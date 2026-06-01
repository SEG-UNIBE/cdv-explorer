from .github_repo import harvest as _github_repo_harvest

_HARVESTERS: dict[str, callable] = {
    "github_repo": _github_repo_harvest,
}


def get_harvester(name: str):
    harvester = _HARVESTERS.get(name)
    if harvester is None:
        available = ", ".join(sorted(_HARVESTERS))
        raise ValueError(f"Unknown harvester '{name}'. Available: {available}")
    return harvester
