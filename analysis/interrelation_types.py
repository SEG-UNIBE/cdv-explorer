"""Shared interrelation-type vocabulary.

The ground-truth curated dataset (analysis/validation/ground_truth.py) and the
LLM extraction approach (analysis/dependencies/) both classify edges into
these four types, so they draw from a single source of truth rather than
duplicating the list. This lives outside both packages deliberately: those
two packages already depend on each other in one direction (analysis.dependencies
imports analysis.validation.ground_truth), so a shared constant needs a
dependency-free home to avoid a circular import.
"""

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
