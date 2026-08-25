from time import perf_counter
from typing import Optional


class StageTimer:
    """Small utility for measuring workflow stage duration."""

    def __init__(self) -> None:
        self.started_at: float | None = None

    def start(self) -> None:
        self.started_at = perf_counter()

    def stop(self) -> float:
        if self.started_at is None:
            raise RuntimeError(
                "StageTimer.stop() called before start()"
            )

        return (
            perf_counter() - self.started_at
        ) * 1000


def stage_metrics(
    *,
    duration_ms: float,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    estimated_cost: Optional[float] = None,
) -> dict:
    return {
        "duration_ms": duration_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost": estimated_cost,
    }