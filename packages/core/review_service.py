from sqlalchemy.orm import Session

from packages.core.checkpoint import WorkflowCheckpoint
from packages.core.review import (
    FindingNotFoundError,
    validate_review_transition,
)
from packages.core.state import FindingStatus, WorkflowState
from packages.db.models.run import AnalysisRun
from packages.db.repositories.reviews import ReviewRepository
from packages.db.repositories.runs import RunRepository


class ReviewService:
    def __init__(
        self,
        run_repository: RunRepository,
        review_repository: ReviewRepository,
        checkpoint: WorkflowCheckpoint,
    ) -> None:
        self.run_repository = run_repository
        self.review_repository = review_repository
        self.checkpoint = checkpoint

    def decide(
        self,
        *,
        session: Session,
        run: AnalysisRun,
        state: WorkflowState,
        finding_id: str,
        decision: FindingStatus,
        comment: str | None = None,
    ) -> WorkflowState:
        finding = next(
            (
                finding
                for finding in state["findings"]
                if finding["finding_id"] == finding_id
            ),
            None,
        )

        if finding is None:
            raise FindingNotFoundError(
                f"Finding {finding_id!r} does not exist"
            )

        current_status = finding["status"]

        validate_review_transition(
            current_status,
            decision,
        )

        # Same decision is intentionally idempotent.
        if current_status == decision:
            return state

        try:
            self.review_repository.create(
                session,
                run_id=run.id,
                finding_id=finding_id,
                decision=decision,
                comment=comment,
                commit=False,
            )

            finding["status"] = decision

            self.checkpoint.save(
                session,
                run,
                state,
                commit=False,
            )

            session.commit()

            return state

        except Exception:
            session.rollback()
            raise