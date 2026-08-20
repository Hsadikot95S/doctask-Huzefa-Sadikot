from pathlib import Path
from multiprocessing import Process
import os
import signal

from packages.agents.graphs.adapter import invoke_workflow_graph
from packages.agents.runner import WorkflowRunner
from packages.agents.workflow import build_stage_graph
from packages.core.checkpoint import WorkflowCheckpoint
from packages.db.database import SessionLocal
from packages.db.repositories.runs import RunRepository


FIXTURE_DOCUMENT = (
    Path(__file__).parents[1]
    / "fixtures"
    / "documents"
    / "contract.pdf"
)


def test_workflow_resumes_from_durable_checkpoint():
    repository = RunRepository()
    checkpoint = WorkflowCheckpoint(repository)

    # ---------------------------------------------------------
    # Worker 1: execute extract_text and persist checkpoint.
    # ---------------------------------------------------------
    with SessionLocal() as session:
        run = repository.create(
            session,
            document_path=str(FIXTURE_DOCUMENT),
        )

        state = checkpoint.restore(run)
        state["status"] = "running"

        run = checkpoint.save(
            session,
            run,
            state,
        )

        graph = build_stage_graph(
            "extract_text",
            session=session,
        )

        state = invoke_workflow_graph(
            graph,
            state,
        )

        state["current_stage"] = "analyze"

        run = checkpoint.save(
            session,
            run,
            state,
        )

        run_id = run.id

        assert run.current_stage == "analyze"

        assert run.state["document_id"] is not None
        assert run.state["extracted_text"] is not None

        assert (
            "SUPERDOCS TEST CONTRACT"
            in run.state["extracted_text"]
        )

        assert (
            "Payment is due within 30 days."
            in run.state["extracted_text"]
        )

        assert (
            run.state["stages"]["extract_text"]["status"]
            == "completed"
        )

    # ---------------------------------------------------------
    # Worker 1 dies here.
    # ---------------------------------------------------------

    # ---------------------------------------------------------
    # Worker 2: starts from PostgreSQL.
    # ---------------------------------------------------------
    runner = WorkflowRunner(repository=repository)

    final_state = runner.run(run_id)

    assert final_state["status"] == "awaiting_review"
    assert final_state["current_stage"] == "review"

    assert final_state["document_id"] is not None
    assert final_state["extracted_text"] is not None

    assert (
        "SUPERDOCS TEST CONTRACT"
        in final_state["extracted_text"]
    )

    assert (
        "Payment is due within 30 days."
        in final_state["extracted_text"]
    )

    assert final_state["findings"]
    assert final_state["findings"][0]["finding_id"] == "F-001"

    # Verify durable state.
    with SessionLocal() as session:
        final_run = repository.get(session, run_id)

        assert final_run is not None
        assert final_run.status == "awaiting_review"
        assert final_run.current_stage == "review"

        assert (
            final_run.state["stages"]["extract_text"]["status"]
            == "completed"
        )

        assert (
            final_run.state["stages"]["analyze"]["status"]
            == "completed"
        )


def test_resume_does_not_reexecute_completed_stage():
    repository = RunRepository()
    checkpoint = WorkflowCheckpoint(repository)

    # ---------------------------------------------------------
    # Worker 1: execute extract_text and durably checkpoint it.
    # ---------------------------------------------------------
    with SessionLocal() as session:
        run = repository.create(
            session,
            document_path=str(FIXTURE_DOCUMENT),
        )

        state = checkpoint.restore(run)
        state["status"] = "running"

        run = checkpoint.save(
            session,
            run,
            state,
        )

        graph = build_stage_graph(
            "extract_text",
            session=session,
        )

        state = invoke_workflow_graph(
            graph,
            state,
        )

        state["current_stage"] = "analyze"

        run = checkpoint.save(
            session,
            run,
            state,
        )

        run_id = run.id

        assert run.current_stage == "analyze"

        assert (
            run.state["stages"]["extract_text"]["status"]
            == "completed"
        )

    # ---------------------------------------------------------
    # Worker 2: fail immediately if extract_text is attempted.
    # ---------------------------------------------------------
    def resume_graph_factory(
        stage: str,
        **kwargs,
    ):
        if stage == "extract_text":
            raise AssertionError(
                "Completed extract_text stage was re-executed"
            )

        return build_stage_graph(
            stage,
            **kwargs,
        )

    runner = WorkflowRunner(
        repository=repository,
        graph_factory=resume_graph_factory,
    )

    final_state = runner.run(run_id)

    assert final_state["status"] == "awaiting_review"
    assert final_state["current_stage"] == "review"
    assert final_state["findings"]


def _worker_checkpoint_then_die(run_id):
    repository = RunRepository()
    checkpoint = WorkflowCheckpoint(repository)

    with SessionLocal() as session:
        run = repository.get(session, run_id)

        if run is None:
            raise RuntimeError(
                f"Run {run_id} not found"
            )

        state = checkpoint.restore(run)
        state["status"] = "running"

        run = checkpoint.save(
            session,
            run,
            state,
        )

        graph = build_stage_graph(
            "extract_text",
            session=session,
        )

        state = invoke_workflow_graph(
            graph,
            state,
        )

        state["current_stage"] = "analyze"

        checkpoint.save(
            session,
            run,
            state,
        )

    # Simulate an actual worker/process crash.
    os.kill(
        os.getpid(),
        signal.SIGKILL,
    )


def test_real_process_restart_resumes_from_durable_checkpoint():
    repository = RunRepository()

    # ---------------------------------------------------------
    # Parent creates the durable run.
    # ---------------------------------------------------------
    with SessionLocal() as session:
        run = repository.create(
            session,
            document_path=str(FIXTURE_DOCUMENT),
        )

        run_id = run.id

    # ---------------------------------------------------------
    # Worker 1: checkpoint extract_text, then actually die.
    # ---------------------------------------------------------
    worker = Process(
        target=_worker_checkpoint_then_die,
        args=(run_id,),
    )

    worker.start()
    worker.join()

    # SIGKILL should terminate the worker.
    assert worker.exitcode == -signal.SIGKILL

    # ---------------------------------------------------------
    # Verify the checkpoint survived the process death.
    # ---------------------------------------------------------
    with SessionLocal() as session:
        persisted_run = repository.get(
            session,
            run_id,
        )

        assert persisted_run is not None
        assert persisted_run.current_stage == "analyze"

        assert persisted_run.state["document_id"] is not None
        assert persisted_run.state["extracted_text"] is not None

        assert (
            "SUPERDOCS TEST CONTRACT"
            in persisted_run.state["extracted_text"]
        )

        assert (
            "Payment is due within 30 days."
            in persisted_run.state["extracted_text"]
        )

        assert (
            persisted_run.state["stages"]["extract_text"]["status"]
            == "completed"
        )

    # ---------------------------------------------------------
    # Worker 2: restart from PostgreSQL.
    # ---------------------------------------------------------
    runner = WorkflowRunner(repository=repository)

    final_state = runner.run(run_id)

    assert final_state["status"] == "awaiting_review"
    assert final_state["current_stage"] == "review"

    assert final_state["findings"]
    assert final_state["findings"][0]["finding_id"] == "F-001"

    # ---------------------------------------------------------
    # Verify final durable state.
    # ---------------------------------------------------------
    with SessionLocal() as session:
        final_run = repository.get(
            session,
            run_id,
        )

        assert final_run is not None
        assert final_run.status == "awaiting_review"
        assert final_run.current_stage == "review"

        assert (
            final_run.state["stages"]["extract_text"]["status"]
            == "completed"
        )

        assert (
            final_run.state["stages"]["analyze"]["status"]
            == "completed"
        )