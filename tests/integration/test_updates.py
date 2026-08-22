from sqlite3 import IntegrityError
from uuid import uuid4

import pytest

from packages.db.database import SessionLocal
from packages.db.models.update import AnalysisUpdate
from packages.db.repositories.documents import DocumentRepository
from packages.db.repositories.runs import RunRepository
from packages.db.repositories.updates import UpdateRepository
from sqlalchemy.exc import IntegrityError

from packages.documents.application import DocumentApplicationService


def test_update_repository_persists_update():
    document_repository = DocumentRepository()
    run_repository = RunRepository()
    update_repository = UpdateRepository()

    source_document_id = uuid4()
    target_run_id = uuid4()

    content_hash = uuid4().hex * 2

    with SessionLocal() as session:
        document_repository.create(
            session,
            document_id=source_document_id,
            filename="amendment.txt",
            content_hash=content_hash,
            mime_type="text/plain",
            size_bytes=50,
        )

        run = run_repository.create(
            session,
            document_path="/documents/contract.txt",
        )

        target_run_id = run.id

        update = update_repository.create(
            session,
            source_document_id=source_document_id,
            target_run_id=target_run_id,
        )

        assert update.id is not None
        assert update.source_document_id == source_document_id
        assert update.target_run_id == target_run_id
        assert update.status == "pending"

    with SessionLocal() as session:
        stored = update_repository.get(session, update.id)

        assert stored is not None
        assert stored.source_document_id == source_document_id
        assert stored.target_run_id == target_run_id
        assert stored.status == "pending"

def test_update_repository_finds_by_source_and_target():
    document_repository = DocumentRepository()
    run_repository = RunRepository()
    update_repository = UpdateRepository()

    source_document_id = uuid4()

    with SessionLocal() as session:
        document_repository.create(
            session,
            document_id=source_document_id,
            filename="amendment-lookup.txt",
            content_hash=uuid4().hex * 2,
            mime_type="text/plain",
            size_bytes=20,
        )

        run = run_repository.create(
            session,
            document_path="/documents/original.txt",
        )

        target_run_id = run.id

        update = update_repository.create(
            session,
            source_document_id=source_document_id,
            target_run_id=target_run_id,
        )

        update_id = update.id

    with SessionLocal() as session:
        stored = update_repository.get_by_source_and_target(
            session,
            source_document_id=source_document_id,
            target_run_id=target_run_id,
        )

        assert stored is not None
        assert stored.id == update_id


def test_update_repository_rejects_duplicate_source_and_target():
    document_repository = DocumentRepository()
    run_repository = RunRepository()
    update_repository = UpdateRepository()

    source_document_id = uuid4()

    with SessionLocal() as session:
        document_repository.create(
            session,
            document_id=source_document_id,
            filename="duplicate-test.txt",
            content_hash=uuid4().hex * 2,
            mime_type="text/plain",
            size_bytes=20,
        )

        run = run_repository.create(
            session,
            document_path="/documents/duplicate-target.txt",
        )

        update_repository.create(
            session,
            source_document_id=source_document_id,
            target_run_id=run.id,
        )

        duplicate = AnalysisUpdate(
            source_document_id=source_document_id,
            target_run_id=run.id,
        )

        session.add(duplicate)

        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()

def test_create_incremental_update_creates_update_and_run():
    application = DocumentApplicationService()

    document_repository = DocumentRepository()
    run_repository = RunRepository()

    with SessionLocal() as session:
        document = document_repository.create(
            session,
            document_id=uuid4(),
            filename="amendment.txt",
            content_hash=uuid4().hex * 2,
            mime_type="text/plain",
            size_bytes=100,
        )

        document.storage_path = "/documents/amendment.txt"
        session.commit()
        session.refresh(document)

        target_run = run_repository.create(
            session,
            document_path="/documents/original.pdf",
        )

        target_run_id = target_run.id
        document_id = document.id


    with SessionLocal() as session:
        update, update_run = application.create_incremental_update(
            session,
            source_document_id=document_id,
            target_run_id=target_run_id,
        )

        assert update.id is not None
        assert update.source_document_id == document_id
        assert update.target_run_id == target_run_id
        assert update.status == "pending"

        assert update_run.id is not None
        assert update_run.id != target_run_id
        assert update_run.state["document_id"] == str(document_id)
        assert update_run.state["update_id"] == str(update.id)
        assert update_run.state["target_run_id"] == str(target_run_id)