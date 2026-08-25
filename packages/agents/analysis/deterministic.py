from packages.agents.analysis.model import AnalysisModel
from packages.core.state import AnalysisResult, Evidence


class DeterministicAnalysisModel(AnalysisModel):
    """
    Deterministic analysis implementation used by the workflow and tests.

    It deliberately does not call an external model provider.
    """

    def analyze(
        self,
        *,
        evidence: list[Evidence],
    ) -> AnalysisResult:
        findings = []

        for item in evidence:
            text = item["text"].strip()

            if not text:
                continue

            findings.append(
                {
                    "finding_id": (
                        f"F-{item['page_number']}"
                    ),
                    "description": (
                        "Document content requires review."
                    ),
                    "status": "pending",
                    "evidence": [
                        (
                            f"page={item['page_number']}: "
                            f"{text[:500]}"
                        )
                    ],
                }
            )

        return {
            "findings": findings,
            "usage": {
                "input_tokens": None,
                "output_tokens": None,
                "estimated_cost": None,
            },
        }