from pathlib import Path
from uuid import UUID
from hashlib import sha256


from sqlalchemy.orm import Session

from packages.db.repositories.documents import DocumentRepository
from packages.db.repositories.runs import RunRepository
from packages.documents.service import DocumentService
from packages.storage.local import LocalDocumentStorage
from packages.db.repositories.updates import UpdateRepository

class DocumentApplicationService:
    """Application boundary for document ingestion and analysis creation."""

    def __init__(
        self,
        document_service: DocumentService | None = None,
        document_repository: DocumentRepository | None = None,
        run_repository: RunRepository | None = None,
        update_repository: UpdateRepository | None = None,
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

        self.update_repository = (
            update_repository or UpdateRepository()
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
            filename = filename,
        )

       
        document_record = self.document_repository.get(session,UUID(document.document_id),)
        if document_record is None:
            raise RuntimeError(
                f"Document {document.document_id} was not persisted"
            )

        document_record.filename = filename
        document_record.storage_path = str(document_path)

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

    def create_incremental_update(
    self,
    session: Session,
    *,
    source_document_id: UUID,
    target_run_id: UUID,
):
        source_document = self.document_repository.get(
            session,
            source_document_id,
        )

        if source_document is None:
            raise ValueError(
                f"Source document {source_document_id} not found"
            )

        target_run = self.run_repository.get(
            session,
            target_run_id,
        )

        if target_run is None:
            raise ValueError(
                f"Target run {target_run_id} not found"
            )

        update = self.update_repository.create(
            session,
            source_document_id=source_document_id,
            target_run_id=target_run_id,
            commit=False,
        )

        update_run = self.run_repository.create(
            session,
            document_path=source_document.storage_path,
            commit=False,
        )

        new_state = dict(update_run.state)

        new_state["document_id"] = str(source_document.id)
        new_state["update_id"] = str(update.id)
        new_state["target_run_id"] = str(target_run.id)

        update_run.state = new_state

        session.flush()

        session.commit()

        session.refresh(update_run)

        return update, update_run