from uuid import uuid4

from packages.db.database import SessionLocal
from packages.db.repositories.documents import DocumentRepository


def test_document_repository_persists_document_and_pages():
    repository = DocumentRepository()

    document_id = uuid4()
    content_hash = uuid4().hex * 2

    with SessionLocal() as session:
        document = repository.create(
            session,
            document_id=document_id,
            filename="contract.txt",
            content_hash=content_hash,
            mime_type="text/plain",
            size_bytes=42,
        )

        repository.create_pages(
            session,
            document_id=document.id,
            pages=[
                (1, "Payment is due within 30 days."),
                (2, "The agreement expires in 2027."),
            ],
        )

        session.commit()

    with SessionLocal() as session:
        stored = repository.get(session, document_id)
        pages = repository.get_pages(session, document_id)

        assert stored is not None
        assert stored.filename == "contract.txt"
        assert stored.content_hash == content_hash
        assert stored.mime_type == "text/plain"
        assert stored.size_bytes == 42

        assert len(pages) == 2
        assert pages[0].page_number == 1
        assert pages[0].text == "Payment is due within 30 days."
        assert pages[1].page_number == 2
        assert pages[1].text == "The agreement expires in 2027."


def test_document_repository_finds_document_by_hash():
    repository = DocumentRepository()

    document_id = uuid4()
    content_hash = uuid4().hex * 2

    with SessionLocal() as session:
        repository.create(
            session,
            document_id=document_id,
            filename="same-content.txt",
            content_hash=content_hash,
            mime_type="text/plain",
            size_bytes=10,
        )

        session.commit()

    with SessionLocal() as session:
        stored = repository.get_by_hash(session, content_hash)

        assert stored is not None
        assert stored.id == document_id