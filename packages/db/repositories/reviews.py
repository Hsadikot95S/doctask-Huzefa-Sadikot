from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.db.models.review import ReviewDecision


class ReviewRepository:
    def create(
        self,
        session: Session,
        *,
        run_id: UUID,
        finding_id: str,
        decision: str,
        comment: str | None = None,
        commit : bool = True,
    ) -> ReviewDecision:
        review = ReviewDecision(
            run_id=run_id,
            finding_id=finding_id,
            decision=decision,
            comment=comment,
        )

        session.add(review)

        if commit:
            session.commit()
            session.refresh(review)

        return review

    def list_for_run(
        self,
        session: Session,
        run_id: UUID,
    ) -> list[ReviewDecision]:
        statement = (
            select(ReviewDecision)
            .where(ReviewDecision.run_id == run_id)
            .order_by(ReviewDecision.created_at, ReviewDecision.id)
        )

        return list(session.scalars(statement).all())