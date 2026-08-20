from pathlib import Path

import pytest

from packages.agents.runner import WorkflowRunner
from packages.db.database import SessionLocal
from packages.db.repositories.runs import RunRepository


def failing_graph_factory(stage: str, **kwargs):
    class FailingGraph:
        def invoke(self, state):
            raise RuntimeError(
                "simulated workflow failure"
            )

    return FailingGraph()


def test_workflow_runner_executes_analysis_run(
    tmp_path: Path,
):
    document_path = tmp_path / "runner.txt"

    document_path.write_text(
        "Payment is due within 30 days.\n"
        "The agreement expires in 2027.",
        encoding="utf-8",
    )

    repository = RunRepository()
    runner = WorkflowRunner(repository=repository)

    with SessionLocal() as session:
        run = repository.create(
            session,
            document_path=str(document_path),
        )

        run_id = run.id

    final_state = runner.run(run_id)

    with SessionLocal() as session:
        persisted_run = repository.get(
            session,
            run_id,
        )

        assert persisted_run is not None
        assert persisted_run.status == "awaiting_review"
        assert persisted_run.current_stage == "review"

        assert persisted_run.state["document_id"] is not None

        assert persisted_run.state["extracted_text"] is not None

        assert final_state["extracted_text"] is not None



        assert (
            "Payment is due within 30 days."
            in persisted_run.state["extracted_text"]
        )

        assert (
            "The agreement expires in 2027."
            in persisted_run.state["extracted_text"]
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

    assert final_state["document_id"] is not None


    assert (
        "Payment is due within 30 days."
        in final_state["extracted_text"]
    )

    assert final_state["findings"]
    assert (
        final_state["findings"][0]["finding_id"]
        == "F-001"
    )


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

    with pytest.raises(
        RuntimeError,
        match="simulated workflow failure",
    ):
        runner.run(run_id)

    with SessionLocal() as session:
        failed_run = repository.get(
            session,
            run_id,
        )

        assert failed_run is not None
        assert failed_run.status == "failed"
        assert failed_run.error == "simulated workflow failure"