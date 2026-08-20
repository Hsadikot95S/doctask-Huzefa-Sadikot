import logging
import os
import signal
import time

from packages.agents.worker import AnalysisWorker


POLL_INTERVAL_SECONDS = float(
    os.getenv(
        "WORKER_POLL_INTERVAL_SECONDS",
        "1.0",
    )
)


logger = logging.getLogger("superdocs.worker")


class WorkerApplication:
    """Long-running worker process lifecycle."""

    def __init__(
        self,
        worker: AnalysisWorker | None = None,
    ) -> None:
        self.worker = worker or AnalysisWorker()
        self._shutdown_requested = False

    def request_shutdown(
        self,
        signum: int,
        frame: object,
    ) -> None:
        logger.info(
            "Shutdown signal received: %s",
            signum,
        )

        self._shutdown_requested = True

    def run(self) -> None:
        logger.info(
            "Worker started: worker_id=%s",
            self.worker.worker_id,
        )

        while not self._shutdown_requested:
            try:
                processed = self.worker.process_one()

                if not processed:
                    time.sleep(
                        POLL_INTERVAL_SECONDS,
                    )

            except Exception:
                logger.exception(
                    "Worker iteration failed",
                )

                # Prevent a transient application error from
                # creating a tight crash loop.
                time.sleep(
                    POLL_INTERVAL_SECONDS,
                )

        logger.info("Worker shutting down")


def main() -> None:
    logging.basicConfig(
        level=os.getenv(
            "LOG_LEVEL",
            "INFO",
        ),
        format=(
            "%(asctime)s %(levelname)s "
            "%(name)s %(message)s"
        ),
    )

    application = WorkerApplication()

    signal.signal(
        signal.SIGTERM,
        application.request_shutdown,
    )

    signal.signal(
        signal.SIGINT,
        application.request_shutdown,
    )

    application.run()


if __name__ == "__main__":
    main()