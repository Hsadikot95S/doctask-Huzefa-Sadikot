from uuid import UUID

from packages.documents.service import (
    DocumentService,
    UnsupportedDocumentError,
)


class FakeRepository:
    def __init__(self):
        self.documents = {}
        self.pages = {}

    def get_by_hash(self, session, content_hash):
        return next(
            (
                document
                for document in self.documents.values()
                if document.content_hash == content_hash
            ),
            None,
        )

    def get_pages(self, session, document_id):
        return self.pages.get(document_id, [])

    def create(
        self,
        session,
        *,
        document_id,
        filename,
        content_hash,
        mime_type,
        size_bytes,
    ):
        from types import SimpleNamespace

        document = SimpleNamespace(
            id=document_id,
            filename=filename,
            content_hash=content_hash,
            mime_type=mime_type,
            size_bytes=size_bytes,
            created_at=None,
        )

        self.documents[document_id] = document

        return document

    def create_pages(
        self,
        session,
        *,
        document_id,
        pages,
    ):
        from types import SimpleNamespace

        records = [
            SimpleNamespace(
                document_id=document_id,
                page_number=page_number,
                text=text,
            )
            for page_number, text in pages
        ]

        self.pages[document_id] = records

        return records


def test_document_service_ingests_txt(tmp_path):
    path = tmp_path / "contract.txt"
    path.write_text(
        "Payment is due within 30 days.",
        encoding="utf-8",
    )

    repository = FakeRepository()
    service = DocumentService(repository=repository)

    document, pages = service.ingest(
        session=None,
        path=path,
    )

    assert document.filename == "contract.txt"
    assert document.mime_type == "text/plain"
    assert document.size_bytes == len(path.read_bytes())
    assert len(document.content_hash) == 64

    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert pages[0].text == "Payment is due within 30 days."

    assert UUID(document.document_id) in repository.documents


def test_document_service_rejects_unsupported_format(tmp_path):
    path = tmp_path / "contract.xyz"
    path.write_text(
        "some content",
        encoding="utf-8",
    )

    service = DocumentService(repository=FakeRepository())

    try:
        service.ingest(
            session=None,
            path=path,
        )
        assert False, "Expected UnsupportedDocumentError"
    except UnsupportedDocumentError:
        pass


def test_document_service_rejects_missing_file(tmp_path):
    path = tmp_path / "missing.txt"

    service = DocumentService(repository=FakeRepository())

    try:
        service.ingest(
            session=None,
            path=path,
        )
        assert False, "Expected FileNotFoundError"
    except FileNotFoundError:
        pass


def test_document_service_is_idempotent_for_same_content(tmp_path):
    path = tmp_path / "contract.txt"
    path.write_text(
        "Same document content.",
        encoding="utf-8",
    )

    repository = FakeRepository()
    service = DocumentService(repository=repository)

    first_document, first_pages = service.ingest(
        session=None,
        path=path,
    )

    second_document, second_pages = service.ingest(
        session=None,
        path=path,
    )

    assert second_document.document_id == first_document.document_id
    assert second_document.content_hash == first_document.content_hash

    assert len(second_pages) == len(first_pages)
    assert second_pages[0].text == first_pages[0].text

    assert len(repository.documents) == 1