from threading import Event, Thread
from uuid import UUID, uuid4

from packages.agents.runner import WorkflowRunner
from packages.db.database import SessionLocal
from packages.db.repositories.runs import RunRepository


DEFAULT_LEASE_SECONDS = 60
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 20


class AnalysisWorker:
    """Executes analysis runs with leased worker ownership."""

    def __init__(
        self,
        repository: RunRepository | None = None,
        runner: WorkflowRunner | None = None,
        worker_id: str | None = None,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
        heartbeat_interval_seconds: float = (
            DEFAULT_HEARTBEAT_INTERVAL_SECONDS
        ),
    ) -> None:
        if lease_seconds <= 0:
            raise ValueError(
                "lease_seconds must be greater than zero"
            )

        if heartbeat_interval_seconds <= 0:
            raise ValueError(
                "heartbeat_interval_seconds must be greater "
                "than zero"
            )

        if heartbeat_interval_seconds >= lease_seconds:
            raise ValueError(
                "heartbeat_interval_seconds must be less "
                "than lease_seconds"
            )

        self.repository = repository or RunRepository()

        self.runner = runner or WorkflowRunner(
            repository=self.repository,
        )

        self.worker_id = worker_id or (
            f"worker-{uuid4()}"
        )

        self.lease_seconds = lease_seconds
        self.heartbeat_interval_seconds = (
            heartbeat_interval_seconds
        )

    def process_run(
        self,
        run_id: UUID,
    ) -> bool:
        """
        Atomically claim and execute a specific run.
        """

        with SessionLocal() as session:
            run = self.repository.claim_run(
                session,
                run_id,
                worker_id=self.worker_id,
                lease_seconds=self.lease_seconds,
            )

            if run is None:
                return False

        stop_event = Event()

        heartbeat_thread = Thread(
            target=self._heartbeat_loop,
            args=(run_id, stop_event),
            daemon=True,
            name=f"heartbeat-{run_id}",
        )

        heartbeat_thread.start()

        try:
            self.runner.run(run_id)

        finally:
            stop_event.set()
            heartbeat_thread.join(
                timeout=self.heartbeat_interval_seconds
                + 1
            )

            self._release_lease(run_id)

        return True

    def process_one(self) -> bool:
        """
        Claim and execute one pending or expired run.
        """

        with SessionLocal() as session:
            run = self.repository.claim_pending(
                session,
                worker_id=self.worker_id,
                lease_seconds=self.lease_seconds,
            )

            if run is None:
                return False

            run_id = run.id

        stop_event = Event()

        heartbeat_thread = Thread(
            target=self._heartbeat_loop,
            args=(run_id, stop_event),
            daemon=True,
            name=f"heartbeat-{run_id}",
        )

        heartbeat_thread.start()

        try:
            self.runner.run(run_id)

        finally:
            stop_event.set()
            heartbeat_thread.join(
                timeout=self.heartbeat_interval_seconds
                + 1
            )

            self._release_lease(run_id)

        return True

    def _heartbeat_loop(
        self,
        run_id: UUID,
        stop_event: Event,
    ) -> None:
        """
        Periodically renew the lease while the workflow runs.
        """

        while not stop_event.wait(
            self.heartbeat_interval_seconds
        ):
            try:
                with SessionLocal() as session:
                    run = self.repository.get(
                        session,
                        run_id,
                    )

                    if run is None:
                        return

                    if run.worker_id != self.worker_id:
                        return

                    self.repository.renew_lease(
                        session,
                        run,
                        worker_id=self.worker_id,
                        lease_seconds=self.lease_seconds,
                    )

            except Exception:
                # The workflow remains responsible for its own
                # failure state. If the heartbeat cannot renew,
                # the current lease will eventually expire and
                # another worker can reclaim the run.
                return

    def _release_lease(
        self,
        run_id: UUID,
    ) -> None:
        """
        Release ownership after workflow execution.
        """

        with SessionLocal() as session:
            run = self.repository.get(
                session,
                run_id,
            )

            if run is None:
                return

            if run.worker_id != self.worker_id:
                return

            self.repository.release_lease(
                session,
                run,
                worker_id=self.worker_id,
            )