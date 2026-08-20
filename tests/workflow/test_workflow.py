from pathlib import Path
from typing import cast

from packages.agents.runner import WorkflowRunner
from packages.agents.workflow import build_graph, build_stage_graph
from packages.core.checkpoint import WorkflowCheckpoint
from packages.core.review_service import ReviewService
from packages.core.state import WorkflowState
from packages.db.database import SessionLocal
from packages.db.repositories.reviews import ReviewRepository
from packages.db.repositories.runs import RunRepository


FIXTURE_DOCUMENT = (
    Path(__file__).parents[1]
    / "fixtures"
    / "documents"
    / "contract.pdf"
)


def test_workflow_builds_and_invokes():
    initial_state = cast(
        WorkflowState,
        {
            "run_id": "test-run",
            "document_path": str(FIXTURE_DOCUMENT),
            "status": "pending",
            "current_stage": "extract_text",
            "document_id": None,
            "extracted_text": None,
            "findings": [],
            "stages": {},
            "error": None,
        },
    )

    with SessionLocal() as session:
        graph = build_graph(session=session)

        result = graph.invoke(initial_state)

        session.commit()

    assert result["document_id"] is not None
    assert result["extracted_text"] is not None

    assert "SUPERDOCS TEST CONTRACT" in result["extracted_text"]
    assert "Payment is due within 30 days." in result["extracted_text"]
    assert "The agreement begins on January 1, 2027." in result["extracted_text"]
    assert "The agreement expires on December 31, 2027." in result["extracted_text"]

    assert len(result["findings"]) == 1
    assert result["findings"][0]["status"] == "pending"

    assert (
        result["stages"]["extract_text"]["status"]
        == "completed"
    )

    assert (
        result["stages"]["analyze"]["status"]
        == "completed"
    )


def test_workflow_stops_at_review_gate():
    repository = RunRepository()
    runner = WorkflowRunner(repository=repository)

    with SessionLocal() as session:
        run = repository.create(
            session,
            document_path=str(FIXTURE_DOCUMENT),
        )

        run_id = run.id

    state = runner.run(run_id)

    assert state["status"] == "awaiting_review"
    assert state["current_stage"] == "review"

    assert state["findings"]

    assert all(
        finding["status"] == "pending"
        for finding in state["findings"]
    )

    with SessionLocal() as session:
        persisted_run = repository.get(session, run_id)

        assert persisted_run is not None
        assert persisted_run.status == "awaiting_review"
        assert persisted_run.current_stage == "review"

        assert persisted_run.state["document_id"] is not None
        assert persisted_run.state["extracted_text"] is not None

        assert (
            persisted_run.state["stages"]["extract_text"]["status"]
            == "completed"
        )

        assert (
            persisted_run.state["stages"]["analyze"]["status"]
            == "completed"
        )


def test_approval_allows_workflow_to_complete():
    repository = RunRepository()
    checkpoint = WorkflowCheckpoint(repository)
    review_repository = ReviewRepository()

    runner = WorkflowRunner(repository=repository)

    with SessionLocal() as session:
        run = repository.create(
            session,
            document_path=str(FIXTURE_DOCUMENT),
        )

        run_id = run.id

    # First execution must stop at review.
    state = runner.run(run_id)

    assert state["status"] == "awaiting_review"
    assert state["current_stage"] == "review"

    # Explicit human decision.
    with SessionLocal() as session:
        run = repository.get(session, run_id)

        assert run is not None

        state = checkpoint.restore(run)

        service = ReviewService(
            run_repository=repository,
            review_repository=review_repository,
            checkpoint=checkpoint,
        )

        state = service.decide(
            session=session,
            run=run,
            state=state,
            finding_id="F-001",
            decision="approved",
        )

    # Resume the workflow.
    final_state = runner.run(run_id)

    assert final_state["status"] == "completed"
    assert final_state["current_stage"] == "complete"

    assert final_state["findings"][0]["status"] == "approved"


def two_finding_graph_factory(
    stage: str,
    **kwargs,
):
    if stage != "analyze":
        return build_stage_graph(
            stage,
            **kwargs,
        )

    class TwoFindingGraph:
        def invoke(self, state: WorkflowState) -> WorkflowState:
            state["findings"] = [
                {
                    "finding_id": "F-001",
                    "description": "First finding",
                    "status": "pending",
                    "evidence": ["page 1"],
                },
                {
                    "finding_id": "F-002",
                    "description": "Second finding",
                    "status": "pending",
                    "evidence": ["page 2"],
                },
            ]

            state["stages"]["analyze"] = {
                "status": "completed",
                "error": None,
            }

            return state

    return TwoFindingGraph()


def test_mixed_review_decisions_are_preserved():
    repository = RunRepository()
    checkpoint = WorkflowCheckpoint(repository)
    review_repository = ReviewRepository()

    runner = WorkflowRunner(
        repository=repository,
        graph_factory=two_finding_graph_factory,
    )

    with SessionLocal() as session:
        run = repository.create(
            session,
            document_path=str(FIXTURE_DOCUMENT),
        )

        run_id = run.id

    state = runner.run(run_id)

    assert state["status"] == "awaiting_review"
    assert state["current_stage"] == "review"

    # Approve F-001.
    with SessionLocal() as session:
        run = repository.get(session, run_id)
        assert run is not None

        state = checkpoint.restore(run)

        service = ReviewService(
            run_repository=repository,
            review_repository=review_repository,
            checkpoint=checkpoint,
        )

        state = service.decide(
            session=session,
            run=run,
            state=state,
            finding_id="F-001",
            decision="approved",
        )

    # Reject F-002.
    with SessionLocal() as session:
        run = repository.get(session, run_id)
        assert run is not None

        state = checkpoint.restore(run)

        service = ReviewService(
            run_repository=repository,
            review_repository=review_repository,
            checkpoint=checkpoint,
        )

        state = service.decide(
            session=session,
            run=run,
            state=state,
            finding_id="F-002",
            decision="rejected",
        )

    final_state = runner.run(run_id)

    assert final_state["status"] == "completed"
    assert final_state["current_stage"] == "complete"

    findings = {
        finding["finding_id"]: finding["status"]
        for finding in final_state["findings"]
    }

    assert findings == {
        "F-001": "approved",
        "F-002": "rejected",
    }