from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from packages.db.exceptions import RunVersionConflict
from packages.db.models.run import AnalysisRun


class RunRepository:
    def create(
        self,
        session: Session,
        document_path: str,
    ) -> AnalysisRun:
        run = AnalysisRun(
            document_path=document_path,
            state={
                "findings": [],
                "stages": {},
                "extracted_text": None,
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        session.add(run)
        session.commit()
        session.refresh(run)

        return run

    def get(
        self,
        session: Session,
        run_id: UUID,
    ) -> AnalysisRun | None:
        return session.get(AnalysisRun, run_id)

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