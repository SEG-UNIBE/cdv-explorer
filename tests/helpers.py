def proposal(
    bip_id,
    *,
    regex_refs=None,
    llm_deps=None,
    requires=None,
    replaces=None,
    proposed_replacement=None,
    status="Draft",
    bip2_score=None,
    bip3_score=None,
    checks=None,
):
    compliance = {}
    if bip2_score is not None:
        compliance["bip2"] = {"score": bip2_score, "checks": checks or []}
    if bip3_score is not None:
        compliance["bip3"] = {"score": bip3_score, "checks": []}
    if compliance:
        compliance["score"] = bip2_score
    preamble = {"bip": bip_id, "title": f"Proposal {bip_id}", "status": status}
    if requires is not None:
        preamble["requires"] = requires
    if replaces is not None:
        preamble["replaces"] = replaces
    if proposed_replacement is not None:
        preamble["proposed_replacement"] = proposed_replacement

    def target_entries(value):
        if value is None:
            return []
        values = value if isinstance(value, list) else [value]
        return [{"target": ref} for ref in values]

    llm_runs = (
        []
        if llm_deps is None
        else [
            {
                "model": "test-model",
                "timestamp": "2026-06-01T00:00:00Z",
                "status": "success",
                "findings": llm_deps,
            }
        ]
    )

    return {
        "raw": {"preamble": preamble},
        "insights": {
            "formal_compliance": compliance,
            "interrelations": {
                "body_extracted_regex": regex_refs or [],
                "body_extracted_llm": llm_runs,
                "preamble_extracted": [
                    {**entry, "type": "requires"} for entry in target_entries(requires)
                ]
                + [{**entry, "type": "replaces"} for entry in target_entries(replaces)]
                + [
                    {**entry, "type": "proposed_replacement"}
                    for entry in target_entries(proposed_replacement)
                ],
            },
        },
    }
