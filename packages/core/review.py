from packages.core.state import FindingStatus


class ReviewError(Exception):
    """Base exception for review operations."""


class FindingNotFoundError(ReviewError):
    """Raised when a finding does not exist."""


class InvalidReviewTransitionError(ReviewError):
    """Raised when a finding cannot transition to the requested status."""




def validate_review_transition(
    current: FindingStatus,
    requested: FindingStatus,
) -> None:
    if current == requested:
        return

    if current != "pending":
        raise InvalidReviewTransitionError(
            f"Cannot transition finding from "
            f"{current!r} to {requested!r}"
        )