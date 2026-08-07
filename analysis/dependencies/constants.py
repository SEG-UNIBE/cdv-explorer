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

# Shared interrelation-type vocabulary: the ground-truth curated dataset and
# the LLM extraction approach both classify edges into these four types, so
# they draw from a single source of truth rather than duplicating the list.
INTERRELATION_TYPE_DEPENDS_ON = "depends_on"
INTERRELATION_TYPE_REFERENCES = "references"
INTERRELATION_TYPE_SUPERSEDES = "supersedes"
INTERRELATION_TYPE_SUPERSEDED_BY = "superseded_by"

INTERRELATION_TYPES = {
    INTERRELATION_TYPE_DEPENDS_ON,
    INTERRELATION_TYPE_REFERENCES,
    INTERRELATION_TYPE_SUPERSEDES,
    INTERRELATION_TYPE_SUPERSEDED_BY,
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
