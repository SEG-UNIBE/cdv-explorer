from collections import defaultdict
from typing import Any, Dict, List

from analysis.proposal_schema import get_formal_compliance
from pipeline.source_context import SourceContext


def _apply_status_alias(status: Any, source_context: SourceContext) -> str:
    value = status or "Unknown"
    return source_context.classification_aliases("status").get(value, value)


def extract_conformity_metrics(
    proposal_data: List[Dict[str, Any]],
    id_field: str = "id",
    source_context: SourceContext | None = None,
) -> Dict[str, Any]:
    context = source_context or SourceContext.default()
    per_proposal = []
    score_values = []
    by_standard = defaultdict(list)
    check_summary: Dict[str, Dict[str, Any]] = {}

    for proposal in proposal_data:
        preamble = proposal.get("raw", {}).get("preamble", {})
        formal_compliance = get_formal_compliance(proposal)
        proposal_id = preamble.get(id_field)
        if proposal_id is None:
            continue

        score = formal_compliance.get("score")
        if score is None:
            score = preamble.get("compliance_score")
        status = _apply_status_alias(preamble.get("status"), context)

        # Discover which standard sub-assessments are present (e.g. bip2, bip3, nip).
        standard_keys = [
            k
            for k, v in formal_compliance.items()
            if isinstance(v, dict) and "checks" in v
        ]
        standard_scores = {
            k: (formal_compliance[k] or {}).get("score") for k in standard_keys
        }

        entry = {
            "id": str(proposal_id),
            "status": status,
            "compliance_score": score,
            # Backward-compat fields - null for ecosystems that don't use BIP standards.
            "bip2_score": standard_scores.get("bip2"),
            "bip3_score": standard_scores.get("bip3"),
            "standard_scores": standard_scores,
            "formal_compliance": formal_compliance,
        }
        per_proposal.append(entry)

        if isinstance(score, (int, float)):
            score_values.append(float(score))

        for standard_key, standard_score in standard_scores.items():
            if isinstance(standard_score, (int, float)):
                by_standard[standard_key].append(float(standard_score))

        for standard_key in standard_keys:
            assessment = formal_compliance.get(standard_key) or {}
            for check in assessment.get("checks", []):
                check_id = check.get("id")
                if not check_id:
                    continue

                summary = check_summary.setdefault(
                    check_id,
                    {
                        "id": check_id,
                        "label": check.get("label"),
                        "category": check.get("category"),
                        "standard": check.get("standard", standard_key),
                        "pass_count": 0,
                        "fail_count": 0,
                        "skip_count": 0,
                    },
                )

                passed = check.get("passed")
                if passed is True:
                    summary["pass_count"] += 1
                elif passed is False:
                    summary["fail_count"] += 1
                else:
                    summary["skip_count"] += 1

    by_standard_avg = {
        standard: round(sum(values) / len(values), 2)
        for standard, values in sorted(by_standard.items())
        if values
    }
    check_summary_payload = []
    for summary in sorted(check_summary.values(), key=lambda item: item["id"]):
        evaluated_count = summary["pass_count"] + summary["fail_count"]
        check_summary_payload.append(
            {
                **summary,
                "evaluated_count": evaluated_count,
                "pass_rate": round((summary["pass_count"] / evaluated_count) * 100, 2)
                if evaluated_count
                else None,
            }
        )

    return {
        "average_score_by_standard": by_standard_avg,
        "check_summary": check_summary_payload,
        "per_proposal": per_proposal,
    }
