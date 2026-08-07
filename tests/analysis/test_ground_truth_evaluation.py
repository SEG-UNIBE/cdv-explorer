from analysis.dependencies.constants import (
    BODY_EXTRACTED_LLM,
    BODY_EXTRACTED_REGEX,
    GROUND_TRUTH_CURATED,
    PREAMBLE_EXTRACTED,
)
from paper.RQ2.ground_truth_evaluation import (
    DOE_TYPE_MAPPING,
    ETA_TYPE_MAPPING,
    build_exact_type_evaluation,
)


def _edge(source, target, extraction_method, relation_type):
    return {
        "source": source,
        "target": target,
        "extraction_method": extraction_method,
        "relation_type": relation_type,
    }


def _approach(evaluation, approach):
    return next(row for row in evaluation["approaches"] if row["approach"] == approach)


def test_eta_mapping_scores_any_subtype_against_any_ground_truth_type():
    network_data = {
        "ground_truth_reviewed_ips": [{"ip": "bips:1"}],
        "dependency_edges": [
            _edge("bips:1", "bips:2", GROUND_TRUTH_CURATED, "supersedes"),
            _edge("bips:1", "bips:3", GROUND_TRUTH_CURATED, "references"),
            _edge("bips:1", "bips:2", PREAMBLE_EXTRACTED, "replaces"),
            _edge("bips:1", "bips:3", BODY_EXTRACTED_LLM, "depends_on"),
            _edge("bips:1", "bips:4", BODY_EXTRACTED_REGEX, "reference"),
        ],
    }

    evaluation = build_exact_type_evaluation(
        network_data,
        type_mapping=ETA_TYPE_MAPPING,
    )

    preamble = _approach(evaluation, PREAMBLE_EXTRACTED)
    llm = _approach(evaluation, BODY_EXTRACTED_LLM)
    regex = _approach(evaluation, BODY_EXTRACTED_REGEX)
    assert preamble["tp"] == 1
    assert preamble["fp"] == 0
    assert llm["tp"] == 1
    assert llm["fp"] == 0
    assert regex["tp"] == 0
    assert regex["fp"] == 1


def test_doe_mapping_scores_only_dependency_oriented_subtypes():
    network_data = {
        "ground_truth_reviewed_ips": [{"ip": "bips:1"}],
        "dependency_edges": [
            _edge("bips:1", "bips:2", GROUND_TRUTH_CURATED, "depends_on"),
            _edge("bips:1", "bips:3", GROUND_TRUTH_CURATED, "supersedes"),
            _edge("bips:1", "bips:2", PREAMBLE_EXTRACTED, "requires"),
            _edge("bips:1", "bips:3", PREAMBLE_EXTRACTED, "replaces"),
            _edge("bips:1", "bips:2", BODY_EXTRACTED_LLM, "depends_on"),
            _edge("bips:1", "bips:3", BODY_EXTRACTED_LLM, "supersedes"),
            _edge("bips:1", "bips:2", BODY_EXTRACTED_REGEX, "reference"),
        ],
    }

    evaluation = build_exact_type_evaluation(
        network_data,
        type_mapping=DOE_TYPE_MAPPING,
    )

    preamble = _approach(evaluation, PREAMBLE_EXTRACTED)
    llm = _approach(evaluation, BODY_EXTRACTED_LLM)
    regex = _approach(evaluation, BODY_EXTRACTED_REGEX)
    assert preamble["tp"] == 1
    assert preamble["fp"] == 0
    assert llm["tp"] == 1
    assert llm["fp"] == 0
    assert regex["tp"] == 1
    assert regex["fp"] == 0
