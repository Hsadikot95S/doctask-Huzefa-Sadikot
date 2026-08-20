from packages.core.checkpoint import WorkflowCheckpoint
from packages.core.state import WorkflowState
from packages.db.database import SessionLocal
from packages.db.repositories.runs import RunRepository


def test_workflow_state_can_be_checkpointed_and_restored():
    repository = RunRepository()
    checkpoint = WorkflowCheckpoint(repository)

    with SessionLocal() as session:
        run = repository.create(
            session,
            document_path="/documents/checkpoint.pdf",
        )

        state: WorkflowState = {
            "run_id": str(run.id),
            "document_path": "/documents/checkpoint.pdf",
            "status": "running",
            "current_stage": "extract_text",
            "document_id": None,
            "extracted_text": "persisted text",
            "findings": [],
            "stages": {
                "extract_text": {
                    "status": "completed",
                    "error": None,
                }
            },
            "error": None,
        }

        updated_run = checkpoint.save(
            session,
            run,
            state,
        )

        restored = checkpoint.restore(updated_run)

        assert restored["run_id"] == str(run.id)
        assert restored["document_path"] == "/documents/checkpoint.pdf"
        assert restored["status"] == "running"
        assert restored["current_stage"] == "extract_text"
        assert restored["extracted_text"] == "persisted text"
        assert restored["stages"]["extract_text"]["status"] == "completed"
        assert restored["error"] is None