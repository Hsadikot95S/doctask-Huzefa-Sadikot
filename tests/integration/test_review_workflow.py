from packages.agents.runner import WorkflowRunner
from packages.core.checkpoint import WorkflowCheckpoint
from packages.core.review_service import ReviewService
from packages.db.database import SessionLocal
from packages.db.repositories.reviews import ReviewRepository
from packages.db.repositories.runs import RunRepository


def approve_all_pending_findings(
    run_id,
    repository,
    checkpoint,
    review_repository,
):
    with SessionLocal() as session:
        run = repository.get(session, run_id)
        assert run is not None

        state = checkpoint.restore(run)

        service = ReviewService(
            run_repository=repository,
            review_repository=review_repository,
            checkpoint=checkpoint,
        )

        for finding in state["findings"]:
            if finding["status"] == "pending":
                service.decide(
                    session=session,
                    run=run,
                    state=state,
                    finding_id=finding["finding_id"],
                    decision="approved",
                )


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


def test_approved_review_allows_workflow_to_complete():
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

    state = runner.run(run_id)

    assert state["status"] == "awaiting_review"

    approve_all_pending_findings(
        run_id,
        repository,
        checkpoint,
        review_repository,
    )

    final_state = runner.run(run_id)

    assert final_state["status"] == "completed"
    assert final_state["current_stage"] == "complete"

    assert all(
        finding["status"] == "approved"
        for finding in final_state["findings"]
    )