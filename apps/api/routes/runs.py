from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from apps.api.schemas.run import RunResponse
from packages.db.database import SessionLocal
from packages.db.repositories.runs import RunRepository


router = APIRouter(
    prefix="/runs",
    tags=["runs"],
)


@router.get(
    "/{run_id}",
    response_model=RunResponse,
    status_code=status.HTTP_200_OK,
)
async def get_run(run_id: UUID) -> RunResponse:
    repository = RunRepository()

    with SessionLocal() as session:
        run = repository.get(
            session,
            run_id,
        )

        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis run {run_id} not found",
            )

        state = run.state or {}

        return RunResponse(
            run_id=run.id,
            document_path=run.document_path,
            status=run.status,
            current_stage=run.current_stage,
            error=run.error,
            findings=state.get(
                "findings",
                [],
            ),
            stages=state.get(
                "stages",
                {},
            ),
        )