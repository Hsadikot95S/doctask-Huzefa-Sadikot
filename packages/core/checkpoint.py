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
                "extracted_text": state["extracted_text"],
            },
            status=state["status"],
            current_stage=state["current_stage"],
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
            status=run.status,
            current_stage=run.current_stage,
            document_id=state.get("document_id"),
            extracted_text=state.get("extracted_text"),
            findings=state.get("findings", []),
            stages=state.get("stages", {}),
            error=run.error,
        )  # type: ignore