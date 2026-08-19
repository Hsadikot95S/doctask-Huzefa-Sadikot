from packages.agents.workflow import build_graph
from typing import cast

from packages.core.state import WorkflowState

from packages.agents.runner import WorkflowRunner
from packages.core.checkpoint import WorkflowCheckpoint
from packages.core.review_service import ReviewService
from packages.db.database import SessionLocal
from packages.db.repositories.reviews import ReviewRepository
from packages.db.repositories.runs import RunRepository
from packages.agents.workflow import build_stage_graph
from packages.core.state import WorkflowState


def test_workflow_builds_and_invokes():
    graph = build_graph()
    initial_state = cast(
    WorkflowState,
    {
        "run_id": "test-run",
        "document_path": "/tmp/test.pdf",
        "status": "pending",
        "current_stage": "extract_text",
        "extracted_text": None,
        "findings": [],
        "stages": {},
        "error": None,
    },
)
    
    result = graph.invoke(initial_state)

    assert result["extracted_text"] == "Dummy extracted text"
    assert len(result["findings"]) == 1
    assert result["findings"][0]["status"] == "pending"
    assert result["stages"]["extract_text"]["status"] == "completed"
    assert result["stages"]["analyze"]["status"] == "completed"


def test_workflow_stops_at_review_gate():
    repository = RunRepository()
    runner = WorkflowRunner(repository=repository)

    with SessionLocal() as session:
        run = repository.create(
            session,
            document_path="/documents/review-gate.pdf",
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
            document_path="/documents/approval.pdf",
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



def two_finding_graph_factory(stage: str):
    if stage != "analyze":
        return build_stage_graph(stage)

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
            document_path="/documents/mixed-review.pdf",
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