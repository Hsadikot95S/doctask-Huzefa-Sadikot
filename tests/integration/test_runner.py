import pytest

from packages.agents.runner import WorkflowRunner
from packages.agents.workflow import build_stage_graph
from packages.core.checkpoint import WorkflowCheckpoint
from packages.db.database import SessionLocal
from packages.db.repositories.runs import RunRepository


def failing_graph_factory(stage: str):
    class FailingGraph:
        def invoke(self, state):
            raise RuntimeError(
                "simulated workflow failure"
            )

    return FailingGraph()

def test_workflow_runner_executes_analysis_run():
    repository = RunRepository()
    runner = WorkflowRunner(repository=repository)

    with SessionLocal() as session:
        run = repository.create(
            session,
            document_path="/documents/runner.pdf",
        )

        run_id = run.id

    final_state = runner.run(run_id)

    with SessionLocal() as session:
        persisted_run = repository.get(session, run_id)

        assert persisted_run is not None
        assert persisted_run.status == "awaiting_review"
        assert persisted_run.current_stage == "review"

        assert persisted_run.state["extracted_text"] == (
            "Dummy extracted text"
        )

        assert persisted_run.state["findings"]
        assert (
            persisted_run.state["findings"][0]["finding_id"]
            == "F-001"
        )

        assert (
            persisted_run.state["stages"]["extract_text"]["status"]
            == "completed"
        )

        assert (
            persisted_run.state["stages"]["analyze"]["status"]
            == "completed"
        )

    assert final_state["run_id"] == str(run_id)
    assert final_state["status"] == "awaiting_review"
    assert final_state["extracted_text"] == "Dummy extracted text"
    assert final_state["findings"]
    assert final_state["findings"][0]["finding_id"] == "F-001"





def test_workflow_failure_is_persisted():
    repository = RunRepository()

    with SessionLocal() as session:
        run = repository.create(
            session,
            document_path="/documents/failure.pdf",
        )

        run_id = run.id

    runner = WorkflowRunner(
        repository=repository,
        graph_factory=failing_graph_factory,
    )

    with pytest.raises(RuntimeError, match="simulated workflow failure"):
        runner.run(run_id)

    with SessionLocal() as session:
        failed_run = repository.get(session, run_id)

        assert failed_run is not None
        assert failed_run.status == "failed"
        assert failed_run.error == "simulated workflow failure"