PREAMBLE_EXTRACTED = "preamble_extracted"
BODY_EXTRACTED_REGEX = "body_extracted_regex"
BODY_EXTRACTED_LLM = "body_extracted_llm"

LEGACY_APPROACH_ALIASES = {
    PREAMBLE_EXTRACTED: "explicit_dependencies",
    BODY_EXTRACTED_REGEX: "explicit_references",
    BODY_EXTRACTED_LLM: "implicit_dependencies",
}

DEPENDENCY_APPROACH_ORDER = [
    PREAMBLE_EXTRACTED,
    BODY_EXTRACTED_REGEX,
    BODY_EXTRACTED_LLM,
]

DEPENDENCY_APPROACH_SHORT_LABELS = {
    PREAMBLE_EXTRACTED: "Preamble",
    BODY_EXTRACTED_REGEX: "Regex",
    BODY_EXTRACTED_LLM: "LLM",
}

DEPENDENCY_APPROACH_LABELS = {
    PREAMBLE_EXTRACTED: "Preamble-Extracted Dependencies",
    BODY_EXTRACTED_REGEX: "Body-Extracted Dependencies (Regex)",
    BODY_EXTRACTED_LLM: "Body-Extracted Dependencies (LLM)",
}

PREAMBLE_DEPENDENCY_SUBTYPES = ("requires", "replaces", "proposed_replacement")
