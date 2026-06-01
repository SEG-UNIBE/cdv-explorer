"""Compliance checker for Bitcoin Improvement Proposals (BIP2 + BIP3 standards)."""
from typing import Any, Dict, List


def check(preamble: Dict[str, Any], content: str, src_config: dict) -> List[dict]:
    """Return a flat list of compliance checks for a single BIP document."""
    from analysis.conformity.compliance import assess_bip2_compliance, assess_bip3_compliance

    preamble_config = src_config["preamble"]
    required_fields: list = preamble_config["required_fields"]
    expected_headlines: dict = preamble_config["expected_headlines"]

    bip2 = assess_bip2_compliance(
        preamble, content,
        required_fields=required_fields,
        expected_headlines=expected_headlines,
    )
    bip3 = assess_bip3_compliance(preamble, content)
    return [*bip2["checks"], *bip3["checks"]]
