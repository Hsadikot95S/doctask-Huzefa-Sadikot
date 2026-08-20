from threading import Event
from uuid import UUID

from packages.agents.worker import AnalysisWorker
from packages.db.database import SessionLocal
from packages.db.repositories.runs import RunRepository


class HeartbeatRunner:
    def __init__(self) -> None:
        self.started = Event()
        self.finished = Event()

    def run(self, run_id: UUID):
        self.started.set()
        self.finished.wait(timeout=5)


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

    runner = HeartbeatRunner()

    worker = AnalysisWorker(
        repository=repository,
        runner=runner,
        worker_id="heartbeat-worker",
        lease_seconds=2,
        heartbeat_interval_seconds=0.5,
    )

    # Run the worker in a background thread so we can inspect
    # the lease while the workflow is still running.
    from threading import Thread

    worker_thread = Thread(
        target=worker.process_run,
        args=(run_id,),
    )

    worker_thread.start()

    assert runner.started.wait(timeout=2)

    # Give the heartbeat enough time to execute at least once.
    import time

    time.sleep(0.8)

    with SessionLocal() as session:
        active_run = repository.get(
            session,
            run_id,
        )

        assert active_run is not None
        assert active_run.worker_id == "heartbeat-worker"
        assert active_run.lease_until is not None
        assert active_run.version >= 3

    runner.finished.set()

    worker_thread.join(timeout=5)

    assert not worker_thread.is_alive()

    with SessionLocal() as session:
        final_run = repository.get(
            session,
            run_id,
        )

        assert final_run is not None
        assert final_run.worker_id is None
        assert final_run.lease_until is None