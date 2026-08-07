# Re-exported from analysis.interrelation_types (a dependency-free module) so
# existing importers of analysis.dependencies.constants keep working; see that
# module's docstring for why the definitions don't live here directly.
from analysis.interrelation_types import (
    INTERRELATION_TYPE_DEPENDS_ON,
    INTERRELATION_TYPE_REFERENCES,
    INTERRELATION_TYPE_SUPERSEDES,
    INTERRELATION_TYPE_SUPERSEDED_BY,
    INTERRELATION_TYPES,
)

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

# Per-approach subtype that represents a technical dependency (as opposed to a
# mere reference/citation or a supersession relation). Mirrors DOE_TYPE_MAPPING
# in paper/RQ2/ground_truth_evaluation.py, but scoped to selecting edges rather
# than mapping them onto a ground-truth type.
DEPENDS_ON_SUBTYPE_BY_APPROACH = {
    PREAMBLE_EXTRACTED: "requires",
    BODY_EXTRACTED_REGEX: "reference",
    BODY_EXTRACTED_LLM: INTERRELATION_TYPE_DEPENDS_ON,
}
