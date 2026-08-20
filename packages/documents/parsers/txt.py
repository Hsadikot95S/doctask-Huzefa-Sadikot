from pathlib import Path

from packages.documents.models import Document, DocumentPage
from packages.documents.parsers.base import DocumentParser


class TXTParser(DocumentParser):
    """Parser for plain-text documents."""

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() == ".txt"

    def parse(
        self,
        document: Document,
        path: Path,
    ) -> list[DocumentPage]:
        text = path.read_text(encoding="utf-8")

        return [
            DocumentPage(
                document_id=document.document_id,
                page_number=1,
                text=text,
            )
        ]
