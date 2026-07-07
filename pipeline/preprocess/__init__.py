from ._enrich import enrich as _enrich_fn
from .nip_tags import extract as _nip_tags_extract
from .rfc_preamble import extract as _rfc_preamble_extract

_EXTRACTORS: dict[str, callable] = {
    "rfc_preamble": _rfc_preamble_extract,
    "nip_tags": _nip_tags_extract,
}


def get_extractor(name: str):
    extractor = _EXTRACTORS.get(name)
    if extractor is None:
        available = ", ".join(sorted(_EXTRACTORS))
        raise ValueError(f"Unknown extractor '{name}'. Available: {available}")
    return extractor


def get_enricher():
    return _enrich_fn
