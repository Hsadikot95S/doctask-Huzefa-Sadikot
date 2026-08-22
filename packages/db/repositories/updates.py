from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.db.models.update import AnalysisUpdate


class UpdateRepository:

    def get(
        self,
        session: Session,
        update_id: UUID,
    ) -> AnalysisUpdate | None:
        return session.get(
            AnalysisUpdate,
            update_id,
        )

    def get_by_source_and_target(
        self,
        session: Session,
        *,
        source_document_id: UUID,
        target_run_id: UUID,
    ) -> AnalysisUpdate | None:
        statement = (
            select(AnalysisUpdate)
            .where(
                AnalysisUpdate.source_document_id
                == source_document_id,
                AnalysisUpdate.target_run_id
                == target_run_id,
            )
        )

        return session.execute(
            statement
        ).scalar_one_or_none()

    def create(
    self,
    session: Session,
    *,
    source_document_id: UUID,
    target_run_id: UUID,
    commit: bool = True,
) -> AnalysisUpdate:
        update = AnalysisUpdate(
            source_document_id=source_document_id,
            target_run_id=target_run_id,
        )

        session.add(update)
        session.flush()

        if commit:
            session.commit()
            session.refresh(update)

        return update