from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from packages.db.repositories.documents import DocumentRepository
from packages.documents.models import Document, DocumentPage
from packages.documents.parsers.base import DocumentParser
from packages.documents.parsers.docx import DOCXParser
from packages.documents.parsers.pdf import PDFParser
from packages.documents.parsers.txt import TXTParser


class UnsupportedDocumentError(ValueError):
    """Raised when no parser supports the document format."""


class DocumentService:
    """Application service for document ingestion and extraction."""

    def __init__(
        self,
        repository: DocumentRepository | None = None,
        parsers: list[DocumentParser] | None = None,
    ) -> None:
        self._repository = repository or DocumentRepository()
        self._parsers = parsers or [
            PDFParser(),
            DOCXParser(),
            TXTParser(),
        ]

    def ingest(
        self,
        session: Session,
        path: Path,
    ) -> tuple[Document, list[DocumentPage]]:
        path = Path(path)

        if not path.is_file():
            raise FileNotFoundError(f"Document not found: {path}")

        content = path.read_bytes()
        content_hash = sha256(content).hexdigest()

        existing = self._repository.get_by_hash(
            session,
            content_hash,
        )

        if existing is not None:
            records = self._repository.get_pages(
                session,
                existing.id,
            )

            document = Document(
                document_id=str(existing.id),
                filename=existing.filename,
                content_hash=existing.content_hash,
                mime_type=existing.mime_type,
                size_bytes=existing.size_bytes,
                created_at=existing.created_at,
            )

            pages = [
                DocumentPage(
                    document_id=str(page.document_id),
                    page_number=page.page_number,
                    text=page.text,
                )
                for page in records
            ]

            return document, pages

        document_id = uuid4()

        document = Document(
            document_id=str(document_id),
            filename=path.name,
            content_hash=content_hash,
            mime_type=self._detect_mime_type(path),
            size_bytes=len(content),
            created_at=self._utc_now(),
        )

        parser = self._select_parser(path)
        pages = parser.parse(document, path)

        self._repository.create(
            session,
            document_id=document_id,
            filename=document.filename,
            content_hash=document.content_hash,
            mime_type=document.mime_type,
            size_bytes=document.size_bytes,
        )

        self._repository.create_pages(
            session,
            document_id=document_id,
            pages=[
                (page.page_number, page.text)
                for page in pages
            ],
        )

        return document, pages

    def _select_parser(self, path: Path) -> DocumentParser:
        for parser in self._parsers:
            if parser.supports(path):
                return parser

        raise UnsupportedDocumentError(
            f"No parser available for document: {path.name}"
        )

    @staticmethod
    def _detect_mime_type(path: Path) -> str:
        mime_types = {
            ".txt": "text/plain",
            ".pdf": "application/pdf",
            ".docx": (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        }

        return mime_types.get(
            path.suffix.lower(),
            "application/octet-stream",
        )

    @staticmethod
    def _utc_now():
        from datetime import datetime, timezone

        return datetime.now(timezone.utc)