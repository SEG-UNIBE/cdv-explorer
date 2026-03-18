from collections import defaultdict
from typing import Any, Dict, List

from ecosystem_config import ACTIVE_ECOSYSTEM


CLASSIFICATION_CONFIG = ACTIVE_ECOSYSTEM.get("classification", {})
STATUS_ALIASES = CLASSIFICATION_CONFIG.get("status_aliases", {})


def _apply_status_alias(status: Any) -> str:
    value = status or "Unknown"
    return STATUS_ALIASES.get(value, value)


def extract_conformity_metrics(proposal_data: List[Dict[str, Any]], id_field: str = "id") -> Dict[str, Any]:
    per_proposal = []
    score_values = []
    by_standard = defaultdict(list)
    check_summary: Dict[str, Dict[str, Any]] = {}

    for proposal in proposal_data:
        preamble = proposal.get("raw", {}).get("preamble", {})
        compliance = proposal.get("compliance", {}) or proposal.get("raw", {}).get("compliance", {})
        proposal_id = preamble.get(id_field)
        if proposal_id is None:
            continue

        score = compliance.get("score")
        if score is None:
            score = preamble.get("compliance_score")
        status = _apply_status_alias(preamble.get("status"))
        bip2_score = (compliance.get("bip2") or {}).get("score")
        bip3_score = (compliance.get("bip3") or {}).get("score")

        entry = {
            "id": str(proposal_id),
            "status": status,
            "compliance_score": score,
            "bip2_score": bip2_score,
            "bip3_score": bip3_score,
            "compliance": compliance,
        }
        per_proposal.append(entry)

        if isinstance(score, (int, float)):
            score_values.append(float(score))

        for standard_key, standard_score in (("bip2", bip2_score), ("bip3", bip3_score)):
            if isinstance(standard_score, (int, float)):
                by_standard[standard_key].append(float(standard_score))

        for standard_key in ("bip2", "bip3"):
            assessment = compliance.get(standard_key) or {}
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
                "pass_rate": round((summary["pass_count"] / evaluated_count) * 100, 2) if evaluated_count else None,
            }
        )

    return {
        "average_score_by_standard": by_standard_avg,
        "check_summary": check_summary_payload,
        "per_proposal": per_proposal,
    }
