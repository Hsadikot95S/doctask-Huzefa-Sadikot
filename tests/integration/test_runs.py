import pytest
from packages.db.database import SessionLocal
from packages.db.repositories.runs import RunRepository
from packages.db.exceptions import RunVersionConflict


def test_analysis_run_can_be_persisted():
    repository = RunRepository()

    with SessionLocal() as session:
        run = repository.create(
            session,
            document_path="/documents/sample.pdf",
        )

        assert run.document_path == "/documents/sample.pdf"
        assert run.status == "pending"
        assert run.current_stage == "extract_text"
        assert run.state["findings"] == []
        assert run.version == 1
        assert run.id is not None

        loaded = repository.get(session, run.id)

        assert loaded is not None
        assert loaded.id == run.id


def test_concurrent_run_update_detects_version_conflict():
    repository = RunRepository()

    with SessionLocal() as session:
        run = repository.create(
            session,
            document_path="/documents/concurrent.pdf",
        )

        run_id = run.id

    with SessionLocal() as session_a:
        worker_a_run = repository.get(session_a, run_id)

        assert worker_a_run is not None
        assert worker_a_run.version == 1

        with SessionLocal() as session_b:
            worker_b_run = repository.get(session_b, run_id)

            assert worker_b_run is not None
            assert worker_b_run.version == 1

            repository.update_state(
                session_a,
                worker_a_run,
                state={
                    "findings": [],
                    "stages": {
                        "extract_text": {
                            "status": "completed",
                            "error": None,
                        }
                    },
                    "extracted_text": "worker A",
                },
                status="running",
                current_stage="analyze",
            )

            assert worker_a_run.version == 2

            with pytest.raises(RunVersionConflict):
                repository.update_state(
                    session_b,
                    worker_b_run,
                    state={
                        "findings": [],
                        "stages": {
                            "extract_text": {
                                "status": "completed",
                                "error": None,
                            }
                        },
                        "extracted_text": "worker B",
                    },
                    status="running",
                    current_stage="analyze",
                )

            with SessionLocal() as verification_session:
                final_run = repository.get(
                    verification_session,
                    run_id,
                )

            assert final_run is not None
            assert final_run.version == 2
            assert final_run.status == "running"
            assert final_run.current_stage == "analyze"
            assert final_run.state["extracted_text"] == "worker A"