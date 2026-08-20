from abc import ABC, abstractmethod
from pathlib import Path

from packages.documents.models import Document, DocumentPage


class DocumentParser(ABC):
    """Interface implemented by all document format parsers."""

    @abstractmethod
    def supports(self, path: Path) -> bool:
        """Return True when this parser can handle the file."""
        raise NotImplementedError

    @abstractmethod
    def parse(
        self,
        document: Document,
        path: Path,
    ) -> list[DocumentPage]:
        """Extract normalized page-level content from a document."""
        raise NotImplementedError
