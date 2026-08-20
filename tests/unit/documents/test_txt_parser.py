from datetime import datetime, timezone

from packages.documents.models import Document
from packages.documents.parsers.txt import TXTParser


def test_txt_parser_extracts_document_content(tmp_path):
    path = tmp_path / "contract.txt"
    path.write_text(
        "Payment is due within 30 days.",
        encoding="utf-8",
    )

    document = Document(
        document_id="doc-001",
        filename="contract.txt",
        content_hash="abc123",
        mime_type="text/plain",
        size_bytes=path.stat().st_size,
        created_at=datetime.now(timezone.utc),
    )

    parser = TXTParser()

    assert parser.supports(path)

    pages = parser.parse(document, path)

    assert len(pages) == 1
    assert pages[0].document_id == "doc-001"
    assert pages[0].page_number == 1
    assert pages[0].text == "Payment is due within 30 days."
