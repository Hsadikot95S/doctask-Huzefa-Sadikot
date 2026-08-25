from abc import ABC, abstractmethod

from packages.core.state import AnalysisResult, Evidence


class AnalysisModel(ABC):
    """Model boundary for structured document analysis."""

    @abstractmethod
    def analyze(
        self,
        *,
        evidence: list[Evidence],
    ) -> AnalysisResult:
        raise NotImplementedError