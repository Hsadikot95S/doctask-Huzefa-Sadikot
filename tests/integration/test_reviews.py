from packages.db.repositories.reviews import ReviewRepository
from packages.db.repositories.runs import RunRepository
from packages.db.database import SessionLocal


def test_review_decision_can_be_persisted():
    run_repository = RunRepository()
    review_repository = ReviewRepository()

    with SessionLocal() as session:
        run = run_repository.create(
            session,
            document_path="/documents/review.pdf",
        )

        review = review_repository.create(
            session,
            run_id=run.id,
            finding_id="F-001",
            decision="approved",
            comment="Looks correct",
        )

        assert review.run_id == run.id
        assert review.finding_id == "F-001"
        assert review.decision == "approved"
        assert review.comment == "Looks correct"


def test_review_decisions_can_be_listed_for_run():
    run_repository = RunRepository()
    review_repository = ReviewRepository()

    with SessionLocal() as session:
        run = run_repository.create(
            session,
            document_path="/documents/review-history.pdf",
        )

        review_repository.create(
            session,
            run_id=run.id,
            finding_id="F-001",
            decision="approved",
        )

        review_repository.create(
            session,
            run_id=run.id,
            finding_id="F-002",
            decision="rejected",
        )

        reviews = review_repository.list_for_run(
            session,
            run.id,
        )

        assert len(reviews) == 2
        assert [review.finding_id for review in reviews] == [
            "F-001",
            "F-002",
        ]