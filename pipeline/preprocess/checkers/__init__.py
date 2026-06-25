from .bip import check as _bip_check
from .nip import check as _nip_check
from .slip import check as _slip_check

_CHECKERS: dict[str, callable] = {
    "bip": _bip_check,
    "nip": _nip_check,
    "slip": _slip_check,
}


def get_checker(name: str):
    checker = _CHECKERS.get(name)
    if checker is None:
        available = ", ".join(sorted(_CHECKERS))
        raise ValueError(f"Unknown compliance checker '{name}'. Available: {available}")
    return checker
