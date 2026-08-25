from packages.agents.analysis.grounding import (
    validate_finding_grounding,
)
from packages.agents.analysis.model import AnalysisModel
from packages.core.state import (
    AnalysisResult,
    Evidence,
)


class AnalysisService:
    """Application boundary around structured document analysis."""

    def __init__(
        self,
        *,
        model: AnalysisModel,
    ) -> None:
        self.model = model

    def analyze(
        self,
        *,
        evidence: list[Evidence],
    ) -> AnalysisResult:
        result = self.model.analyze(
            evidence=evidence,
        )

        grounded_findings = []

        for finding in result["findings"]:
            grounded_findings.append(
                validate_finding_grounding(
                    finding,
                    evidence,
                )
            )

        return {
            "findings": grounded_findings,
            "usage": result["usage"],
        }