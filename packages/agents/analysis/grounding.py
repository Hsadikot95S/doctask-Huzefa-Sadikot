from packages.core.state import Evidence, Finding


def validate_finding_grounding(
    finding: Finding,
    evidence: list[Evidence],
) -> Finding:
    """
    Ensure a finding contains evidence from the supplied source material.

    Unsupported findings are rejected rather than silently persisted.
    """

    if not finding["evidence"]:
        raise ValueError(
            f"Finding {finding['finding_id']} has no evidence"
        )

    source_text = "\n".join(
        item["text"]
        for item in evidence
    )

    for citation in finding["evidence"]:
        if not citation:
            raise ValueError(
                f"Finding {finding['finding_id']} "
                "contains empty evidence"
            )

    if not source_text.strip():
        raise ValueError(
            f"Finding {finding['finding_id']} "
            "cannot be grounded against empty evidence"
        )

    return finding