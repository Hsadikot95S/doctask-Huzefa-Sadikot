from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from packages.db.exceptions import RunVersionConflict
from packages.db.models.run import AnalysisRun


DEFAULT_LEASE_SECONDS = 60


class RunRepository:
    def create(
        self,
        session: Session,
        document_path: str,
        *,
        commit:bool = True
    ) -> AnalysisRun:
        run = AnalysisRun(
            document_path=document_path,
            state={
                "findings": [],
                "stages": {},
                "document_id": None,
                "update_id": None,
                "target_run_id": None,
                "extracted_text": None,
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        session.add(run)
        session.flush()

        if commit:
            session.commit()
            session.refresh(run)

        return run

    def get(
        self,
        session: Session,
        run_id: UUID,
    ) -> AnalysisRun | None:
        return session.get(
            AnalysisRun,
            run_id,
        )

    def update_state(
        self,
        session: Session,
        run: AnalysisRun,
        *,
        state: dict,
        status: str,
        current_stage: str,
        error: str | None = None,
        commit: bool = True,
    ) -> AnalysisRun:
        expected_version = run.version

        statement = (
            update(AnalysisRun)
            .where(
                AnalysisRun.id == run.id,
                AnalysisRun.version == expected_version,
            )
            .values(
                state=state,
                status=status,
                current_stage=current_stage,
                error=error,
                version=expected_version + 1,
            )
            .returning(AnalysisRun)
        )

        result = session.execute(statement)

        updated_run = result.scalar_one_or_none()

        if updated_run is None:
            session.rollback()

            raise RunVersionConflict(
                f"Run {run.id} was modified by another worker"
            )

        if commit:
            session.commit()
            session.refresh(updated_run)

        return updated_run

    def claim_pending(
        self,
        session: Session,
        *,
        worker_id: str,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
    ) -> AnalysisRun | None:
        """
        Atomically claim one pending or expired run.

        PostgreSQL row locking ensures concurrent workers
        cannot claim the same run.

        An expired lease allows a previously running job to
        be reclaimed after its worker disappears.
        """

        now = datetime.now(timezone.utc)

        lease_until = (
            now + timedelta(seconds=lease_seconds)
        )

        statement = (
            select(AnalysisRun)
            .where(
                (
                    AnalysisRun.status == "pending"
                )
                |
                (
                    (AnalysisRun.status == "running")
                    & (
                        AnalysisRun.lease_until <= now
                    )
                )
            )
            .order_by(
                AnalysisRun.created_at,
            )
            .with_for_update(
                skip_locked=True,
            )
            .limit(1)
        )

        run = session.execute(
            statement
        ).scalar_one_or_none()

        if run is None:
            return None

        run.status = "running"
        run.worker_id = worker_id
        run.lease_until = lease_until
        run.version += 1

        session.commit()
        session.refresh(run)

        return run

    def claim_run(
        self,
        session: Session,
        run_id: UUID,
        *,
        worker_id: str,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
    ) -> AnalysisRun | None:
        """
        Atomically claim a specific pending or expired run.
        """

        now = datetime.now(timezone.utc)

        lease_until = (
            now + timedelta(seconds=lease_seconds)
        )

        statement = (
            select(AnalysisRun)
            .where(
                AnalysisRun.id == run_id,
                (
                    (AnalysisRun.status == "pending")
                    |
                    (
                        (AnalysisRun.status == "running")
                        & (
                            AnalysisRun.lease_until <= now
                        )
                    )
                ),
            )
            .with_for_update()
            .limit(1)
        )

        run = session.execute(
            statement
        ).scalar_one_or_none()

        if run is None:
            return None

        run.status = "running"
        run.worker_id = worker_id
        run.lease_until = lease_until
        run.version += 1

        session.commit()
        session.refresh(run)

        return run

    def renew_lease(
        self,
        session: Session,
        run: AnalysisRun,
        *,
        worker_id: str,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
    ) -> AnalysisRun:
        """
        Extend the lease for the worker that currently owns
        the run.
        """

        now = datetime.now(timezone.utc)

        statement = (
            update(AnalysisRun)
            .where(
                AnalysisRun.id == run.id,
                AnalysisRun.status == "running",
                AnalysisRun.worker_id == worker_id,
                AnalysisRun.version == run.version,
                AnalysisRun.lease_until > now,
            )
            .values(
                lease_until=(
                    now
                    + timedelta(
                        seconds=lease_seconds
                    )
                ),
                version=run.version + 1,
            )
            .returning(AnalysisRun)
        )

        result = session.execute(statement)

        updated_run = result.scalar_one_or_none()

        if updated_run is None:
            session.rollback()

            raise RunVersionConflict(
                f"Lease for run {run.id} "
                "could not be renewed"
            )

        session.commit()
        session.refresh(updated_run)

        return updated_run

    def release_lease(
        self,
        session: Session,
        run: AnalysisRun,
        *,
        worker_id: str,
    ) -> AnalysisRun:
        """
        Release worker ownership.

        Used when a run reaches a terminal or review state.
        """

        statement = (
            update(AnalysisRun)
            .where(
                AnalysisRun.id == run.id,
                AnalysisRun.worker_id == worker_id,
                AnalysisRun.version == run.version,
            )
            .values(
                worker_id=None,
                lease_until=None,
                version=run.version + 1,
            )
            .returning(AnalysisRun)
        )

        result = session.execute(statement)

        updated_run = result.scalar_one_or_none()

        if updated_run is None:
            session.rollback()

            raise RunVersionConflict(
                f"Run {run.id} ownership changed"
            )

        session.commit()
        session.refresh(updated_run)

        return updated_run

    