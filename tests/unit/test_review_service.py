from typing import cast

import pytest

from packages.core.checkpoint import WorkflowCheckpoint
from packages.core.review import (
    FindingNotFoundError,
    InvalidReviewTransitionError,
)
from packages.core.review_service import ReviewService
from packages.core.state import WorkflowState
from packages.db.repositories.runs import RunRepository


class FakeSession:
    def __init__(self):
        self.rollback_called = False
        self.commit_called = False

    def rollback(self):
        self.rollback_called = True

    def commit(self):
        self.commit_called = True


class FakeReviewRepository:
    def __init__(self):
        self.decisions = []

    def create(
        self,
        session,
        *,
        run_id,
        finding_id,
        decision,
        comment=None,
        commit=True,
    ):
        self.decisions.append(
            {
                "run_id": run_id,
                "finding_id": finding_id,
                "decision": decision,
                "comment": comment,
            }
        )


class FakeRunRepository:
    pass


class FakeCheckpoint:
    def __init__(self):
        self.saved_states = []

    def save(
        self,
        session,
        run,
        state,
        *,
        commit=True,
    ):
        self.saved_states.append(
            {
                "run": run,
                "state": state,
                "commit": commit,
            }
        )

        return run


class FakeRun:
    def __init__(self):
        self.id = "00000000-0000-0000-0000-000000000001"


class FailingCheckpoint:
    def save(
        self,
        session,
        run,
        state,
        *,
        commit=True,
    ):
        raise RuntimeError("checkpoint failed")


def make_state() -> WorkflowState:
    return cast(
        WorkflowState,
        {
            "run_id": "00000000-0000-0000-0000-000000000001",
            "document_path": "/documents/test.pdf",
            "status": "awaiting_review",
            "current_stage": "review",
            "extracted_text": "test",
            "findings": [
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
            ],
            "stages": {},
            "error": None,
        },
    )


@pytest.fixture
def session():
    return FakeSession()


@pytest.fixture
def review_repository():
    return FakeReviewRepository()


@pytest.fixture
def checkpoint():
    return FakeCheckpoint()


@pytest.fixture
def run():
    return FakeRun()


@pytest.fixture
def service(review_repository, checkpoint):
    return ReviewService(
        run_repository=cast(RunRepository, FakeRunRepository()),
        review_repository=review_repository,
        checkpoint=cast(WorkflowCheckpoint, checkpoint),
    )


def test_review_rolls_back_when_checkpoint_fails(
    session,
    review_repository,
    run,
):
    service = ReviewService(
        run_repository=cast(RunRepository, FakeRunRepository()),
        review_repository=review_repository,
        checkpoint=cast(WorkflowCheckpoint, FailingCheckpoint()),
    )

    state = make_state()

    with pytest.raises(RuntimeError, match="checkpoint failed"):
        service.decide(
            session=session,
            run=run,
            state=state,
            finding_id="F-001",
            decision="approved",
        )

    assert session.rollback_called is True
    assert session.commit_called is False


def test_pending_finding_can_be_approved(
    service,
    review_repository,
    session,
    run,
):
    state = make_state()

    result = service.decide(
        session=session,
        run=run,
        state=state,
        finding_id="F-001",
        decision="approved",
    )

    assert result["findings"][0]["status"] == "approved"
    assert len(review_repository.decisions) == 1
    assert review_repository.decisions[0]["decision"] == "approved"


def test_pending_finding_can_be_rejected(
    service,
    review_repository,
    session,
    run,
):
    state = make_state()

    result = service.decide(
        session=session,
        run=run,
        state=state,
        finding_id="F-001",
        decision="rejected",
    )

    assert result["findings"][0]["status"] == "rejected"
    assert len(review_repository.decisions) == 1
    assert review_repository.decisions[0]["decision"] == "rejected"


def test_same_approval_is_idempotent(
    service,
    review_repository,
):
    state = make_state()
    state["findings"][0]["status"] = "approved"

    result = service.decide(
        session=None,
        run=None,
        state=state,
        finding_id="F-001",
        decision="approved",
    )

    assert result["findings"][0]["status"] == "approved"
    assert review_repository.decisions == []


def test_same_rejection_is_idempotent(
    service,
    review_repository,
):
    state = make_state()
    state["findings"][0]["status"] = "rejected"

    result = service.decide(
        session=None,
        run=None,
        state=state,
        finding_id="F-001",
        decision="rejected",
    )

    assert result["findings"][0]["status"] == "rejected"
    assert review_repository.decisions == []


def test_approved_finding_cannot_be_rejected(service):
    state = make_state()
    state["findings"][0]["status"] = "approved"

    with pytest.raises(InvalidReviewTransitionError):
        service.decide(
            session=None,
            run=None,
            state=state,
            finding_id="F-001",
            decision="rejected",
        )


def test_rejected_finding_cannot_be_approved(service):
    state = make_state()
    state["findings"][0]["status"] = "rejected"

    with pytest.raises(InvalidReviewTransitionError):
        service.decide(
            session=None,
            run=None,
            state=state,
            finding_id="F-001",
            decision="approved",
        )


def test_nonexistent_finding_raises_error(service):
    state = make_state()

    with pytest.raises(FindingNotFoundError):
        service.decide(
            session=None,
            run=None,
            state=state,
            finding_id="F-999",
            decision="approved",
        )