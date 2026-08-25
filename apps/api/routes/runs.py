from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from apps.api.schemas.run import RunResponse
from packages.core.checkpoint import WorkflowCheckpoint
from packages.core.review_service import ReviewService
from packages.core.state import FindingStatus
from packages.db.database import SessionLocal
from packages.db.repositories.reviews import ReviewRepository
from packages.db.repositories.runs import RunRepository
from packages.agents.runner import WorkflowRunner


router = APIRouter(
    prefix="/runs",
    tags=["runs"],
)


class ReviewRequest(BaseModel):
    finding_id: str
    decision: str
    comment: str | None = None


def _get_run_or_404(
    repository: RunRepository,
    session,
    run_id: UUID,
):
    run = repository.get(session, run_id)

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis run {run_id} not found",
        )

    return run


@router.get(
    "/{run_id}",
    response_model=RunResponse,
    status_code=status.HTTP_200_OK,
)
async def get_run(run_id: UUID) -> RunResponse:
    repository = RunRepository()

    with SessionLocal() as session:
        run = _get_run_or_404(
            repository,
            session,
            run_id,
        )

        state = run.state or {}

        return RunResponse(
            run_id=run.id,
            document_path=run.document_path,
            status=run.status,
            current_stage=run.current_stage,
            error=run.error,
            findings=state.get("findings", []),
            stages=state.get("stages", {}),
        )


@router.post(
    "/{run_id}/resume",
    response_model=RunResponse,
    status_code=status.HTTP_200_OK,
)
async def resume_run(run_id: UUID) -> RunResponse:
    repository = RunRepository()

    with SessionLocal() as session:
        _get_run_or_404(
            repository,
            session,
            run_id,
        )

    try:
        runner = WorkflowRunner(
            repository=repository,
        )

        state = runner.run(run_id)

        return RunResponse(
            run_id=run_id,
            document_path=state.get(
                "document_path",
                "",
            ),
            status=state["status"],
            current_stage=state["current_stage"],
            error=state.get("error"),
            findings=state.get("findings", []), # pyright: ignore[reportArgumentType]
            stages=state.get("stages", {}), # pyright: ignore[reportArgumentType]
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/{run_id}/findings",
    status_code=status.HTTP_200_OK,
)
async def get_findings(run_id: UUID):
    repository = RunRepository()

    with SessionLocal() as session:
        run = _get_run_or_404(
            repository,
            session,
            run_id,
        )

        state = run.state or {}

        return {
            "run_id": str(run.id),
            "status": run.status,
            "findings": state.get("findings", []),
        }


@router.post(
    "/{run_id}/review",
    response_model=RunResponse,
    status_code=status.HTTP_200_OK,
)
async def review_finding(
    run_id: UUID,
    request: ReviewRequest,
) -> RunResponse:
    if request.decision not in {
        "approved",
        "rejected",
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "decision must be "
                "'approved' or 'rejected'"
            ),
        )

    run_repository = RunRepository()
    review_repository = ReviewRepository()

    with SessionLocal() as session:
        run = _get_run_or_404(
            run_repository,
            session,
            run_id,
        )

        checkpoint = WorkflowCheckpoint(
            run_repository,
        )

        review_service = ReviewService(
            run_repository=run_repository,
            review_repository=review_repository,
            checkpoint=checkpoint,
        )

        state = checkpoint.restore(run)

        try:
            updated_state = review_service.decide(
                session=session,
                run=run,
                state=state,
                finding_id=request.finding_id,
                decision=request.decision,  # type: ignore[arg-type]
                comment=request.comment,
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    # Resume outside the review transaction.
    runner = WorkflowRunner(
        repository=run_repository,
    )

    resumed_state = runner.run(run_id)

    return RunResponse(
        run_id=run_id,
        document_path=resumed_state.get(
            "document_path",
            "",
        ),
        status=resumed_state["status"],
        current_stage=resumed_state["current_stage"],
        error=resumed_state.get("error"),
        findings=resumed_state.get("findings", []), # pyright: ignore[reportArgumentType]
        stages=resumed_state.get("stages", {}), # pyright: ignore[reportArgumentType]
    )