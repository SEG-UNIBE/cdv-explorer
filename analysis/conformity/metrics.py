from collections import Counter, defaultdict
from typing import Any, Dict, List


def extract_conformity_metrics(proposal_data: List[Dict[str, Any]], id_field: str = "bip") -> Dict[str, Any]:
    per_proposal = []
    score_values = []
    by_status = defaultdict(list)

    for proposal in proposal_data:
        preamble = proposal.get("raw", {}).get("preamble", {})
        proposal_id = preamble.get(id_field)
        if proposal_id is None:
            continue

        score = preamble.get("compliance_score")
        status = preamble.get("status") or "Unknown"

        entry = {
            "id": str(proposal_id),
            "status": status,
            "compliance_score": score,
        }
        per_proposal.append(entry)

        if isinstance(score, (int, float)):
            score_values.append(float(score))
            by_status[status].append(float(score))

    histogram = Counter(int(v // 10) * 10 for v in score_values)
    histogram_payload = [
        {"bucket": f"{bucket}-{bucket + 9}", "count": count}
        for bucket, count in sorted(histogram.items())
    ]

    by_status_avg = {
        status: round(sum(values) / len(values), 2)
        for status, values in sorted(by_status.items())
        if values
    }

    overall_avg = round(sum(score_values) / len(score_values), 2) if score_values else None

    return {
        "overall_average_score": overall_avg,
        "score_distribution": histogram_payload,
        "average_score_by_status": by_status_avg,
        "per_proposal": per_proposal,
    }
