from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from packages.agents.worker import AnalysisWorker
from packages.db.database import SessionLocal
from packages.db.repositories.runs import RunRepository


FIXTURE_DOCUMENT = Path(
    "tests/fixtures/documents/contract.txt"
)


def test_concurrent_workers_claim_different_runs():
    repository = RunRepository()

    with SessionLocal() as session:
        run_1 = repository.create(
            session,
            document_path=str(FIXTURE_DOCUMENT),
        )

        run_2 = repository.create(
            session,
            document_path=str(FIXTURE_DOCUMENT),
        )

        run_1_id = run_1.id
        run_2_id = run_2.id

    worker_1 = AnalysisWorker(
        repository=repository,
        worker_id="worker-1",
    )

    worker_2 = AnalysisWorker(
        repository=repository,
        worker_id="worker-2",
    )

    def claim(worker, run_id):
        with SessionLocal() as session:
            claimed = repository.claim_run(
                session,
                run_id,
                worker_id=worker.worker_id,
                lease_seconds=60,
            )

            return (
                claimed.id
                if claimed is not None
                else None
            )

    with ThreadPoolExecutor(
        max_workers=2
    ) as executor:

        futures = [
            executor.submit(
                claim,
                worker_1,
                run_1_id,
            ),
            executor.submit(
                claim,
                worker_2,
                run_2_id,
            ),
        ]

        results = [
            future.result()
            for future in futures
        ]

    claimed_ids = {
        run_id
        for run_id in results
        if run_id is not None
    }

    assert claimed_ids == {
        run_1_id,
        run_2_id,
    }

    with SessionLocal() as session:
        persisted_1 = repository.get(
            session,
            run_1_id,
        )

        persisted_2 = repository.get(
            session,
            run_2_id,
        )

        assert persisted_1 is not None
        assert persisted_2 is not None

        assert persisted_1.status == "running"
        assert persisted_2.status == "running"

        assert persisted_1.worker_id == "worker-1"
        assert persisted_2.worker_id == "worker-2"

def test_concurrent_workers_cannot_claim_same_run():
    repository = RunRepository()

    with SessionLocal() as session:
        run = repository.create(
            session,
            document_path=str(FIXTURE_DOCUMENT),
        )

        run_id = run.id

    worker_1 = AnalysisWorker(
        repository=repository,
        worker_id="worker-1",
    )

    worker_2 = AnalysisWorker(
        repository=repository,
        worker_id="worker-2",
    )

    def claim(worker):
        with SessionLocal() as session:
            claimed = repository.claim_run(
                session,
                run_id,
                worker_id=worker.worker_id,
                lease_seconds=60,
            )

            return (
                claimed.worker_id
                if claimed is not None
                else None
            )

    with ThreadPoolExecutor(
        max_workers=2
    ) as executor:

        results = list(
            executor.map(
                claim,
                [worker_1, worker_2],
            )
        )

    assert sorted(
        result
        for result in results
        if result is not None
    ) == ["worker-1"]

    with SessionLocal() as session:
        persisted = repository.get(
            session,
            run_id,
        )

        assert persisted is not None
        assert persisted.status == "running"
        assert persisted.worker_id == "worker-1"