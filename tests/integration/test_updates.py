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

from packages.agents.runner import WorkflowRunner

from tests.integration.test_restartability import FIXTURE_DOCUMENT


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


def test_incremental_update_run_executes():
    application = DocumentApplicationService()
    document_repository = DocumentRepository()
    run_repository = RunRepository()
    runner = WorkflowRunner()

    with SessionLocal() as session:
        # ---------------------------------------------------------
        # Create the amendment/source document.
        # ---------------------------------------------------------
        document = document_repository.create(
            session,
            document_id=uuid4(),
            filename="amendment.txt",
            content_hash=uuid4().hex * 2,
            mime_type="text/plain",
            size_bytes=100,
            storage_path=str(FIXTURE_DOCUMENT),
        )

        document_id = document.id

        # ---------------------------------------------------------
        # Create the existing analysis run that the update targets.
        # ---------------------------------------------------------
        target_run = run_repository.create(
            session,
            document_path=str(FIXTURE_DOCUMENT),
        )

        target_run_id = target_run.id

    # -------------------------------------------------------------
    # Create the incremental update and its dedicated run.
    # -------------------------------------------------------------
    with SessionLocal() as session:
        update, update_run = application.create_incremental_update(
            session,
            source_document_id=document_id,
            target_run_id=target_run_id,
        )

        update_run_id = update_run.id

        assert update.id is not None
        assert update_run_id is not None

        assert update.source_document_id == document_id
        assert update.target_run_id == target_run_id

        assert update_run.state["document_id"] == str(document_id)
        assert update_run.state["update_id"] == str(update.id)
        assert update_run.state["target_run_id"] == str(target_run_id)

    # -------------------------------------------------------------
    # Execute the incremental run.
    # -------------------------------------------------------------
    final_state = runner.run(update_run_id)

    # -------------------------------------------------------------
    # The existing runner stops at the review boundary.
    # -------------------------------------------------------------
    assert final_state["document_id"] == str(document_id)
    assert final_state["update_id"] == str(update.id)
    assert final_state["target_run_id"] == str(target_run_id)

    assert final_state["status"] == "awaiting_review"
    assert final_state["current_stage"] == "review"

    assert final_state["findings"]


def test_incremental_update_preserves_existing_findings():
    application = DocumentApplicationService()
    document_repository = DocumentRepository()
    run_repository = RunRepository()
    runner = WorkflowRunner()

    with SessionLocal() as session:
        # ---------------------------------------------------------
        # Create the amendment/source document.
        # ---------------------------------------------------------
        document = document_repository.create(
            session,
            document_id=uuid4(),
            filename="amendment.txt",
            content_hash=uuid4().hex * 2,
            mime_type="text/plain",
            size_bytes=100,
            storage_path=str(FIXTURE_DOCUMENT),
        )

        document_id = document.id

        # ---------------------------------------------------------
        # Create the existing target analysis run.
        # ---------------------------------------------------------
        target_run = run_repository.create(
            session,
            document_path=str(FIXTURE_DOCUMENT),
        )

        # Persist the existing findings through the repository
        # instead of mutating the JSONB column directly.
        target_run = run_repository.update_state(
            session,
            target_run,
            state={
                **target_run.state,
                "findings": [
                    {
                        "finding_id": "F-001",
                        "description": "Existing approved finding",
                        "status": "approved",
                        "evidence": ["source.pdf:page=1"],
                    },
                    {
                        "finding_id": "F-002",
                        "description": "Existing rejected finding",
                        "status": "rejected",
                        "evidence": ["source.pdf:page=2"],
                    },
                ],
            },
            status=target_run.status,
            current_stage=target_run.current_stage,
            error=target_run.error,
        )

        target_run_id = target_run.id

        # ---------------------------------------------------------
        # Create the incremental update and dedicated run.
        # ---------------------------------------------------------
        update, update_run = (
            application.create_incremental_update(
                session,
                source_document_id=document_id,
                target_run_id=target_run_id,
            )
        )

        update_run_id = update_run.id

        # ---------------------------------------------------------
        # Execute the incremental update.
        # ---------------------------------------------------------
        final_state = runner.run(update_run_id)

        # ---------------------------------------------------------
        # Existing findings must remain unchanged.
        # ---------------------------------------------------------
        findings = final_state["findings"]

        finding_1 = next(
            finding
            for finding in findings
            if finding["finding_id"] == "F-001"
        )

        finding_2 = next(
            finding
            for finding in findings
            if finding["finding_id"] == "F-002"
        )

        assert finding_1["status"] == "approved"
        assert finding_2["status"] == "rejected"

        assert (
            finding_1["description"]
            == "Existing approved finding"
        )

        assert (
            finding_2["description"]
            == "Existing rejected finding"
        )

        # ---------------------------------------------------------
        # Incremental analysis must add a new pending finding.
        # ---------------------------------------------------------
        new_findings = [
            finding
            for finding in findings
            if finding["finding_id"].startswith("UPDATE-")
        ]

        assert len(new_findings) == 1

        new_finding = new_findings[0]

        assert new_finding["status"] == "pending"