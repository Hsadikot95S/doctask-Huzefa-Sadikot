from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.db.models.document import DocumentPageRecord, DocumentRecord


class DocumentRepository:
    def create(
        self,
        session: Session,
        *,
        document_id: UUID,
        filename: str,
        content_hash: str,
        mime_type: str,
        size_bytes: int,
        storage_path: str | None = None,
    ) -> DocumentRecord:
        """
        Create a document record.

        Kept as the backward-compatible repository API used by
        existing integration tests and callers.

        New application code should prefer `accept()` when the
        durable storage path is known.
        """

        document = DocumentRecord(
            id=document_id,
            filename=filename,
            content_hash=content_hash,
            mime_type=mime_type,
            size_bytes=size_bytes,
            storage_path=storage_path,
        )

        session.add(document)
        session.commit()
        session.refresh(document)

        return document

    def accept(
        self,
        session: Session,
        *,
        document_id: UUID,
        filename: str,
        content_hash: str,
        mime_type: str,
        size_bytes: int,
        storage_path: str,
    ) -> DocumentRecord:
        """
        Persist a newly ingested document with durable storage metadata.
        """

        document = DocumentRecord(
            id=document_id,
            filename=filename,
            content_hash=content_hash,
            mime_type=mime_type,
            size_bytes=size_bytes,
            storage_path=storage_path,
        )

        session.add(document)
        session.commit()
        session.refresh(document)

        return document

    def get(
        self,
        session: Session,
        document_id: UUID,
    ) -> DocumentRecord | None:
        return session.get(DocumentRecord, document_id)

    def get_by_hash(
        self,
        session: Session,
        content_hash: str,
    ) -> DocumentRecord | None:
        statement = select(DocumentRecord).where(
            DocumentRecord.content_hash == content_hash
        )

        return session.execute(statement).scalar_one_or_none()

    def create_pages(
        self,
        session: Session,
        *,
        document_id: UUID,
        pages: list[tuple[int, str]],
    ) -> list[DocumentPageRecord]:
        records = [
            DocumentPageRecord(
                document_id=document_id,
                page_number=page_number,
                text=text,
            )
            for page_number, text in pages
        ]

        session.add_all(records)
        session.commit()

        return records

    def get_pages(
        self,
        session: Session,
        document_id: UUID,
    ) -> list[DocumentPageRecord]:
        statement = (
            select(DocumentPageRecord)
            .where(
                DocumentPageRecord.document_id == document_id
            )
            .order_by(DocumentPageRecord.page_number)
        )

        return list(
            session.execute(statement).scalars().all()
        )