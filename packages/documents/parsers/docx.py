from pathlib import Path

from docx import Document as DOCXDocument

from packages.documents.models import Document, DocumentPage
from packages.documents.parsers.base import DocumentParser


class DOCXParser(DocumentParser):
    """Parser for DOCX documents."""

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() == ".docx"

    def parse(
        self,
        document: Document,
        path: Path,
    ) -> list[DocumentPage]:
        source = DOCXDocument(path)

        paragraphs = [
            paragraph.text
            for paragraph in source.paragraphs
            if paragraph.text.strip()
        ]

        text = "\n".join(paragraphs)

        return [
            DocumentPage(
                document_id=document.document_id,
                page_number=1,
                text=text,
            )
        ]
