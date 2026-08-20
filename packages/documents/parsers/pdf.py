from pathlib import Path

from pypdf import PdfReader

from packages.documents.models import Document, DocumentPage
from packages.documents.parsers.base import DocumentParser


class PDFParser(DocumentParser):
    """Parser for text-based PDF documents."""

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() == ".pdf"

    def parse(
        self,
        document: Document,
        path: Path,
    ) -> list[DocumentPage]:
        reader = PdfReader(path)

        return [
            DocumentPage(
                document_id=document.document_id,
                page_number=page_number,
                text=page.extract_text() or "",
            )
            for page_number, page in enumerate(reader.pages, start=1)
        ]
