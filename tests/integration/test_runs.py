from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from apps.api.main import app
from packages.db.database import SessionLocal
from packages.db.exceptions import RunVersionConflict
from packages.db.repositories.runs import RunRepository
import time

from packages.agents.worker import AnalysisWorker
from packages.db.database import SessionLocal
from packages.db.repositories.runs import RunRepository

client = TestClient(app)


def test_get_run_returns_persisted_run():
    repository = RunRepository()

    with SessionLocal() as session:
        run = repository.create(
            session,
            document_path="/documents/test.pdf",
        )

        run_id = run.id

    response = client.get(
        f"/runs/{run_id}",
    )

    assert response.status_code == 200

    body = response.json()

    assert body["run_id"] == str(run_id)
    assert body["document_path"] == "/documents/test.pdf"
    assert body["status"] == "pending"
    assert body["current_stage"] == "extract_text"
    assert body["error"] is None
    assert body["findings"] == []
    assert body["stages"] == {}


def test_get_run_returns_404_for_unknown_run():
    run_id = uuid4()

    response = client.get(
        f"/runs/{run_id}",
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": f"Analysis run {run_id} not found",
    }


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

        loaded = repository.get(
            session,
            run.id,
        )

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
        worker_a_run = repository.get(
            session_a,
            run_id,
        )

        assert worker_a_run is not None
        assert worker_a_run.version == 1

        with SessionLocal() as session_b:
            worker_b_run = repository.get(
                session_b,
                run_id,
            )

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


def test_worker_can_renew_its_lease():
    repository = RunRepository()

    with SessionLocal() as session:
        run = repository.create(
            session,
            document_path="/documents/lease-renewal.pdf",
        )

        run_id = run.id

    with SessionLocal() as session:
        claimed_run = repository.claim_run(
            session,
            run_id,
            worker_id="worker-a",
            lease_seconds=60,
        )

        assert claimed_run is not None
        assert claimed_run.status == "running"
        assert claimed_run.worker_id == "worker-a"
        assert claimed_run.lease_until is not None

        original_version = claimed_run.version
        original_lease = claimed_run.lease_until

        renewed_run = repository.renew_lease(
            session,
            claimed_run,
            worker_id="worker-a",
            lease_seconds=120,
        )

        assert renewed_run.worker_id == "worker-a"
        assert renewed_run.lease_until is not None
        assert renewed_run.lease_until > original_lease
        assert renewed_run.version == original_version + 1


def test_worker_cannot_renew_another_workers_lease():
    repository = RunRepository()

    with SessionLocal() as session:
        run = repository.create(
            session,
            document_path="/documents/lease-owner.pdf",
        )

        run_id = run.id

    with SessionLocal() as session:
        claimed_run = repository.claim_run(
            session,
            run_id,
            worker_id="worker-a",
            lease_seconds=60,
        )

        assert claimed_run is not None

        with pytest.raises(RunVersionConflict):
            repository.renew_lease(
                session,
                claimed_run,
                worker_id="worker-b",
                lease_seconds=120,
            )


def test_expired_lease_cannot_be_renewed():
    repository = RunRepository()

    with SessionLocal() as session:
        run = repository.create(
            session,
            document_path="/documents/expired-lease.pdf",
        )

        run_id = run.id

    with SessionLocal() as session:
        claimed_run = repository.claim_run(
            session,
            run_id,
            worker_id="worker-a",
            lease_seconds=60,
        )

        assert claimed_run is not None

        claimed_run.lease_until = (
            datetime.now(timezone.utc)
            - timedelta(seconds=1)
        )

        session.commit()
        session.refresh(claimed_run)

        with pytest.raises(RunVersionConflict):
            repository.renew_lease(
                session,
                claimed_run,
                worker_id="worker-a",
                lease_seconds=120,
            )


def test_lease_renewal_increments_version():
    repository = RunRepository()

    with SessionLocal() as session:
        run = repository.create(
            session,
            document_path="/documents/lease-version.pdf",
        )

        run_id = run.id

    with SessionLocal() as session:
        claimed_run = repository.claim_run(
            session,
            run_id,
            worker_id="worker-a",
            lease_seconds=60,
        )

        assert claimed_run is not None

        version_before_renewal = claimed_run.version

        renewed_run = repository.renew_lease(
            session,
            claimed_run,
            worker_id="worker-a",
            lease_seconds=120,
        )

        assert (
            renewed_run.version
            == version_before_renewal + 1
        )

        with SessionLocal() as verification_session:
            persisted_run = repository.get(
                verification_session,
                run_id,
            )

        assert persisted_run is not None
        assert (
            persisted_run.version
            == version_before_renewal + 1
        )





class SlowRunner:
    def __init__(self, delay: float = 2.0):
        self.delay = delay

    def run(self, run_id):
        time.sleep(self.delay)


def test_worker_renews_lease_during_long_running_work():
    repository = RunRepository()

    with SessionLocal() as session:
        run = repository.create(
            session,
            document_path=(
                "tests/fixtures/documents/"
                "contract.pdf"
            ),
        )

        run_id = run.id

    worker = AnalysisWorker(
        repository=repository,
        runner=SlowRunner(delay=2.0),
        worker_id="heartbeat-worker",
    )

    processed = worker.process_run(run_id)

    assert processed is True

    with SessionLocal() as session:
        completed_run = repository.get(
            session,
            run_id,
        )

        assert completed_run is not None
        assert completed_run.worker_id is None
        assert completed_run.lease_until is None