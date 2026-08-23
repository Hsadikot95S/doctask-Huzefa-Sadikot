from sqlalchemy.orm import Session

from packages.core.state import WorkflowState
from packages.db.models.run import AnalysisRun
from packages.db.repositories.runs import RunRepository


class WorkflowCheckpoint:
    def __init__(self, repository: RunRepository):
        self.repository = repository

    def save(
        self,
        session: Session,
        run: AnalysisRun,
        state: WorkflowState,
        *,
        commit: bool = True,
    ) -> AnalysisRun:
        return self.repository.update_state(
            session,
            run,
            state={
                "findings": state["findings"],
                "stages": state["stages"],
                "document_id": state["document_id"],
                "update_id": state.get("update_id"),
                "target_run_id": state.get("target_run_id"),
                "extracted_text": state["extracted_text"],
            },
            status=state["status"], # pyright: ignore[reportGeneralTypeIssues]
            current_stage=state["current_stage"], # pyright: ignore[reportGeneralTypeIssues]
            error=state["error"],
            commit=commit,
        )

    def restore(
        self,
        run: AnalysisRun,
    ) -> WorkflowState:
        state = run.state

        return WorkflowState(
            run_id=str(run.id),
            document_path=run.document_path,
            status=run.status,  # type: ignore
            current_stage=run.current_stage,  # type: ignore
            update_id=state.get("update_id"),
            target_run_id=state.get("target_run_id"),
            document_id=state.get("document_id"),
            extracted_text=state.get("extracted_text"),
            findings=state.get("findings", []),
            stages=state.get("stages", {}),
            error=run.error,
        )  # type: ignore