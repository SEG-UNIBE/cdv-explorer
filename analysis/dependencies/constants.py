# Re-exported from analysis.interrelation_types (a dependency-free module) so
# existing importers of analysis.dependencies.constants keep working; see that
# module's docstring for why the definitions don't live here directly.
from analysis.interrelation_types import (
    INTERRELATION_TYPE_DEPENDS_ON,
    INTERRELATION_TYPE_REFERENCES,
    INTERRELATION_TYPE_SUPERSEDED_BY,
    INTERRELATION_TYPE_SUPERSEDES,
    INTERRELATION_TYPES,
)

__all__ = [
    "INTERRELATION_TYPE_DEPENDS_ON",
    "INTERRELATION_TYPE_REFERENCES",
    "INTERRELATION_TYPE_SUPERSEDES",
    "INTERRELATION_TYPE_SUPERSEDED_BY",
    "INTERRELATION_TYPES",
    "PREAMBLE_EXTRACTED",
    "BODY_EXTRACTED_REGEX",
    "BODY_EXTRACTED_LLM",
    "GROUND_TRUTH_CURATED",
    "DEPENDENCY_APPROACH_ORDER",
    "DEPENDENCY_PAIRWISE_COMPARISON_ORDER",
    "DEPENDENCY_APPROACH_SHORT_LABELS",
    "DEPENDENCY_APPROACH_LABELS",
    "PAIRWISE_TYPE_WILDCARD",
    "CANONICAL_TYPE_BY_APPROACH_SUBTYPE",
]

PREAMBLE_EXTRACTED = "preamble_extracted"
BODY_EXTRACTED_REGEX = "body_extracted_regex"
BODY_EXTRACTED_LLM = "body_extracted_llm"
GROUND_TRUTH_CURATED = "ground_truth_curated"

DEPENDENCY_APPROACH_ORDER = [
    PREAMBLE_EXTRACTED,
    BODY_EXTRACTED_REGEX,
    BODY_EXTRACTED_LLM,
    GROUND_TRUTH_CURATED,
]

DEPENDENCY_PAIRWISE_COMPARISON_ORDER = [
    PREAMBLE_EXTRACTED,
    BODY_EXTRACTED_REGEX,
    BODY_EXTRACTED_LLM,
]

DEPENDENCY_APPROACH_SHORT_LABELS = {
    PREAMBLE_EXTRACTED: "Preamble",
    BODY_EXTRACTED_REGEX: "Regex",
    BODY_EXTRACTED_LLM: "LLM",
    GROUND_TRUTH_CURATED: "Ground Truth",
}

DEPENDENCY_APPROACH_LABELS = {
    PREAMBLE_EXTRACTED: "Preamble-Extracted Dependencies",
    BODY_EXTRACTED_REGEX: "Body-Extracted Dependencies (Regex)",
    BODY_EXTRACTED_LLM: "Body-Extracted Dependencies (LLM)",
    GROUND_TRUTH_CURATED: "Ground Truth (Human-Curated)",
}

# Sentinel canonical "type" meaning "matches any type." Regex extraction is a
# plain identifier match with no semantic understanding, so it cannot commit
# to depends_on/references/supersedes/superseded_by specifically; pinning it
# to one of those would make it agree with other approaches only when they
# happen to pick that same arbitrary type. Wildcard resolution (see
# _expand_wildcard_pairwise_keys_for_typed_universe in metrics.py) instead lets a regex edge
# agree with whatever canonical type the other approach recorded for the same
# directed pair, mirroring GT_TYPE_ALL in paper/RQ2/ground_truth_evaluation.py.
PAIRWISE_TYPE_WILDCARD = "*"

# Fixed mapping from each approach's extracted subtype onto the canonical
# interrelation-type vocabulary (depends_on/references/supersedes/
# superseded_by), or PAIRWISE_TYPE_WILDCARD for subtypes with no real type
# signal. Used for "exact type" pairwise comparison: two approaches' edges
# only count as the same when both the directed pair AND this canonical type
# agree. Every subtype an approach extracts is included here (unlike a single
# "counts as depends_on" filter), so e.g. a preamble `replaces` edge is
# compared against other approaches' `supersedes`-typed edges rather than
# being dropped from the comparison.
CANONICAL_TYPE_BY_APPROACH_SUBTYPE = {
    PREAMBLE_EXTRACTED: {
        "requires": INTERRELATION_TYPE_DEPENDS_ON,
        "replaces": INTERRELATION_TYPE_SUPERSEDES,
        "proposed_replacement": INTERRELATION_TYPE_SUPERSEDED_BY,
    },
    BODY_EXTRACTED_REGEX: {
        "reference": PAIRWISE_TYPE_WILDCARD,
    },
    BODY_EXTRACTED_LLM: {
        INTERRELATION_TYPE_DEPENDS_ON: INTERRELATION_TYPE_DEPENDS_ON,
        INTERRELATION_TYPE_REFERENCES: INTERRELATION_TYPE_REFERENCES,
        INTERRELATION_TYPE_SUPERSEDES: INTERRELATION_TYPE_SUPERSEDES,
        INTERRELATION_TYPE_SUPERSEDED_BY: INTERRELATION_TYPE_SUPERSEDED_BY,
    },
}
