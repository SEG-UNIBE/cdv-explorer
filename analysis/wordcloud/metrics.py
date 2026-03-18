from collections import Counter
from typing import Any, Dict, List

def extract_wordcloud_metrics(
    proposal_data: List[Dict[str, Any]],
    id_field: str,
    top_n: int = 200,
) -> Dict[str, Any]:
    aggregate_counter: Counter[str] = Counter()
    per_proposal: List[Dict[str, Any]] = []
    included = 0

    for proposal in proposal_data:
        preamble = proposal.get("raw", {}).get("preamble", {})
        proposal_id = preamble.get(id_field)
        if proposal_id is None:
            continue

        insights = proposal.get("insights", {})
        word_list = insights.get("word_list")
        if not isinstance(word_list, dict):
            continue

        included += 1
        numeric_word_counts = {
            str(word): int(count)
            for word, count in word_list.items()
            if isinstance(count, (int, float)) and int(count) > 0
        }

        aggregate_counter.update(numeric_word_counts)
        per_proposal.append(
            {
                "id": str(proposal_id),
                "unique_terms": len(numeric_word_counts),
                "total_terms": sum(numeric_word_counts.values()),
            }
        )

    top_words = [
        {"word": word, "count": count}
        for word, count in aggregate_counter.most_common(top_n)
    ]

    return {
        "meta": {
            "proposal_count": included,
            "unique_terms_total": len(aggregate_counter),
            "top_n": top_n,
            "generated_metrics": [
                "top_words",
                "per_proposal",
            ],
        },
        "top_words": top_words,
        "per_proposal": sorted(per_proposal, key=lambda row: row["id"]),
    }
