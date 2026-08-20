from datetime import datetime, timezone

from pypdf import PdfWriter

from packages.documents.models import Document
from packages.documents.parsers.pdf import PDFParser


def test_pdf_parser_supports_pdf(tmp_path):
    path = tmp_path / "contract.pdf"

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)

    with path.open("wb") as file:
        writer.write(file)

    document = Document(
        document_id="doc-pdf-001",
        filename="contract.pdf",
        content_hash="abc123",
        mime_type="application/pdf",
        size_bytes=path.stat().st_size,
        created_at=datetime.now(timezone.utc),
    )

    parser = PDFParser()

    assert parser.supports(path)

    pages = parser.parse(document, path)

    assert len(pages) == 1
    assert pages[0].document_id == document.document_id
    assert pages[0].page_number == 1
