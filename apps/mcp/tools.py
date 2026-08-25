from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP

from packages.agents.runner import WorkflowRunner
from packages.core.review_service import ReviewService
from packages.db.database import SessionLocal
from packages.db.repositories.runs import RunRepository
from packages.db.repositories.updates import UpdateRepository
from packages.documents.application import (
    DocumentApplicationService,
)
from packages.core.checkpoint import WorkflowCheckpoint
from packages.db.repositories.reviews import ReviewRepository

def _serialize_run(run: Any) -> dict[str, Any]:
    state = run.state or {}

    return {
        "run_id": str(run.id),
        "status": run.status,
        "current_stage": run.current_stage,
        "error": run.error,
        "state": state,
    }


def _serialize_update(update: Any) -> dict[str, Any]:
    return {
        "update_id": str(update.id),
        "source_document_id": str(
            update.source_document_id
        ),
        "target_run_id": str(
            update.target_run_id
        ),
        "run_id": str(update.run_id)
        if getattr(update, "run_id", None)
        else None,
        "status": getattr(
            update,
            "status",
            None,
        ),
    }


def register_tools(mcp: FastMCP) -> None:

    document_service = DocumentApplicationService()
    run_repository = RunRepository()
    update_repository = UpdateRepository()
    checkpoint = WorkflowCheckpoint(
        run_repository
        )

    review_repository = ReviewRepository()

    review_service = ReviewService(
        run_repository=run_repository,
        review_repository=review_repository,
        checkpoint=checkpoint,
    )
    runner = WorkflowRunner(
        repository=run_repository,
    )

    @mcp.tool(
        name="create_document",
        description=(
            "Ingest a document and create its initial "
            "durable analysis run."
        ),
    )
    def create_document(
        document_path: str,
    ) -> dict[str, Any]:

        path = Path(document_path)

        if not path.exists():
            raise ValueError(
                f"Document does not exist: {document_path}"
            )

        if not path.is_file():
            raise ValueError(
                f"Document path is not a file: {document_path}"
            )

        with SessionLocal() as session:
            document, run = (
                document_service.ingest_and_create_run(
                    session,
                    document_path=str(path), # pyright: ignore[reportCallIssue]
                )
            )

            return {
                "document_id": str(document.id),
                "run_id": str(run.id),
                "status": run.status,
                "current_stage": run.current_stage,
            }








    @mcp.tool(
        name="start_analysis",
        description=(
            "Execute an analysis run from its durable "
            "checkpoint."
        ),
    )
    def start_analysis(
        run_id: str,
    ) -> dict[str, Any]:

        parsed_run_id = UUID(run_id)

        state = runner.run(
            parsed_run_id,
        )

        return {
            "run_id": str(parsed_run_id),
            "status": state["status"],
            "current_stage": state[
                "current_stage"
            ],
            "findings": state.get(
                "findings",
                [],
            ),
            "error": state.get(
                "error"
            ),
        }

    @mcp.tool(
        name="get_run",
        description=(
            "Return the durable state of an analysis run."
        ),
    )
    def get_run(
        run_id: str,
    ) -> dict[str, Any]:

        parsed_run_id = UUID(run_id)

        with SessionLocal() as session:
            run = run_repository.get(
                session,
                parsed_run_id,
            )

            if run is None:
                raise ValueError(
                    f"Analysis run {run_id} not found"
                )

            return _serialize_run(run)

    @mcp.tool(
        name="get_findings",
        description=(
            "Return findings associated with an analysis run."
        ),
    )
    def get_findings(
        run_id: str,
    ) -> dict[str, Any]:

        parsed_run_id = UUID(run_id)

        with SessionLocal() as session:
            run = run_repository.get(
                session,
                parsed_run_id,
            )

            if run is None:
                raise ValueError(
                    f"Analysis run {run_id} not found"
                )

            state = run.state or {}

            return {
                "run_id": str(parsed_run_id),
                "status": run.status,
                "findings": state.get(
                    "findings",
                    [],
                ),
            }

    @mcp.tool(
        name="review_finding",
        description=(
            "Approve or reject a finding through the "
            "human-review boundary."
        ),
    )
    def review_finding(
        run_id: str,
        finding_id: str,
        decision: str,
        comment: str | None = None,
    ) -> dict[str, Any]:

        parsed_run_id = UUID(run_id)

        if decision not in {
            "approved",
            "rejected",
        }:
            raise ValueError(
                "decision must be 'approved' or 'rejected'"
            )

        with SessionLocal() as session:
            run = run_repository.get(session, parsed_run_id)

            if run is None:
                raise ValueError(f"Analysis run {run_id} not found")

            state = checkpoint.restore(run)


            updated_state = review_service.decide(
                session=session,
                run=run,
                state=state,
                finding_id=finding_id,
                decision=decision, # pyright: ignore[reportArgumentType]
                comment=comment,
            )

            resumed_state = WorkflowRunner().run(run.id)


            return {
                "run_id": str(run.id),
                "finding_id": finding_id,
                "decision": decision,
                "comment": comment,
                "status": resumed_state["status"],
                "findings": resumed_state[
                    "findings"
                ],
            }







    @mcp.tool(
        name="create_incremental_update",
        description=(
            "Create a durable incremental update against "
            "an existing analysis run."
        ),
    )
    def create_incremental_update(
        source_document_id: str,
        target_run_id: str,
    ) -> dict[str, Any]:

        with SessionLocal() as session:

            update, run = (
                document_service.create_incremental_update(
                    session,
                    source_document_id=UUID(
                        source_document_id
                    ),
                    target_run_id=UUID(
                        target_run_id
                    ),
                )
            )

            return {
                "update_id": str(update.id),
                "run_id": str(run.id),
                "source_document_id": source_document_id,
                "target_run_id": target_run_id,
                "status": run.status,
                "current_stage": run.current_stage,
            }

    @mcp.tool(
        name="get_update",
        description=(
            "Return the durable state of an incremental update."
        ),
    )
    def get_update(
        update_id: str,
    ) -> dict[str, Any]:

        parsed_update_id = UUID(update_id)

        with SessionLocal() as session:

            update = update_repository.get(
                session,
                parsed_update_id,
            )

            if update is None:
                raise ValueError(
                    f"Incremental update "
                    f"{update_id} not found"
                )

            return _serialize_update(update)
