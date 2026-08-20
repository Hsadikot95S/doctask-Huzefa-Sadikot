from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from packages.db.repositories.documents import DocumentRepository
from packages.db.repositories.runs import RunRepository
from packages.documents.service import DocumentService
from packages.storage.local import LocalDocumentStorage
from hashlib import sha256

class DocumentApplicationService:
    """Application boundary for document ingestion and analysis creation."""

    def __init__(
        self,
        document_service: DocumentService | None = None,
        document_repository: DocumentRepository | None = None,
        run_repository: RunRepository | None = None,
        storage: LocalDocumentStorage | None = None,
    ) -> None:
        self.document_service = (
            document_service or DocumentService()
        )

        self.document_repository = (
            document_repository or DocumentRepository()
        )

        self.run_repository = (
            run_repository or RunRepository()
        )

        self.storage = (
            storage or LocalDocumentStorage()
        )

    def ingest_and_create_run(
        self,
        session: Session,
        *,
        filename: str,
        content: bytes,
    ):
        """Store, ingest, persist, and create an analysis run."""

        content_hash = sha256(content).hexdigest()


        existing_document = (
            self.document_repository.get_by_hash(
                session,
                content_hash,
            )
        )

        if existing_document is not None:
            document_path = self._restore_or_get_file(
                existing_document,
                content,
            )

            pages = self.document_repository.get_pages(
                session,
                existing_document.id,
            )

            run = self.run_repository.create(
                session,
                document_path=str(document_path),
            )

            run.state["document_id"] = str(
                existing_document.id
            )

            session.commit()
            session.refresh(run)

            return existing_document, pages, run

        document_path = self.storage.store(
            filename=filename,
            content=content,
        )

        document, pages = self.document_service.ingest(
            session,
            document_path,
        )

        document_record = self.document_repository.accept(
            session,
            document_id=UUID(document.document_id),
            filename=document.filename,
            content_hash=document.content_hash,
            mime_type=document.mime_type,
            size_bytes=document.size_bytes,
            storage_path=str(document_path),
        )

        self.document_repository.create_pages(
            session,
            document_id=document_record.id,
            pages=[
                (
                    page.page_number,
                    page.text,
                )
                for page in pages
            ],
        )

        run = self.run_repository.create(
            session,
            document_path=str(document_path),
        )

        run.state["document_id"] = str(
            document_record.id
        )

        session.commit()
        session.refresh(run)

        return document_record, pages, run

    def _restore_or_get_file(
        self,
        document,
        content: bytes,
    ) -> Path:
        if document.storage_path:
            path = Path(document.storage_path)

            if path.is_file():
                return path

        path = self.storage.store(
            filename=document.filename,
            content=content,
        )

        document.storage_path = str(path)

        return path