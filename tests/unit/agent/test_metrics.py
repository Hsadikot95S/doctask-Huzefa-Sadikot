import time

import pytest

from packages.core.metrics import (
    StageTimer,
    stage_metrics,
)


def test_stage_timer_requires_start_before_stop():
    timer = StageTimer()

    with pytest.raises(
        RuntimeError,
        match="called before start",
    ):
        timer.stop()


def test_stage_timer_returns_duration_in_milliseconds():
    timer = StageTimer()

    timer.start()
    time.sleep(0.001)

    duration_ms = timer.stop()

    assert duration_ms >= 0
    assert duration_ms < 10_000


def test_stage_metrics_preserves_all_values():
    metrics = stage_metrics(
        duration_ms=125.5,
        input_tokens=100,
        output_tokens=50,
        estimated_cost=0.0025,
    )

    assert metrics == {
        "duration_ms": 125.5,
        "input_tokens": 100,
        "output_tokens": 50,
        "estimated_cost": 0.0025,
    }


def test_stage_metrics_defaults_optional_values_to_none():
    metrics = stage_metrics(
        duration_ms=25.0,
    )

    assert metrics == {
        "duration_ms": 25.0,
        "input_tokens": None,
        "output_tokens": None,
        "estimated_cost": None,
    }