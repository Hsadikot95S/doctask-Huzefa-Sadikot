from packages.agents.runner import WorkflowRunner
from packages.db.database import SessionLocal
from packages.db.repositories.runs import RunRepository


def test_run_persists_stage_metrics():
    repository = RunRepository()
    runner = WorkflowRunner(
        repository=repository,
    )

    with SessionLocal() as session:
        run = repository.create(
            session,
            document_path="tests/fixtures/documents/contract.txt",
        )

        run_id = run.id

    state = runner.run(run_id)

    extract_stage = state["stages"]["extract_text"]
    assert extract_stage is not None

    extract_metrics = extract_stage["metrics"]
    assert extract_metrics is not None

    assert extract_metrics["duration_ms"] >= 0
    assert extract_metrics["input_tokens"] is None
    assert extract_metrics["output_tokens"] is None
    assert extract_metrics["estimated_cost"] is None

    analyze_stage = state["stages"]["analyze"]
    assert analyze_stage is not None

    analyze_metrics = analyze_stage["metrics"]
    assert analyze_metrics is not None

    assert analyze_metrics["duration_ms"] >= 0
    assert "input_tokens" in analyze_metrics
    assert "output_tokens" in analyze_metrics
    assert "estimated_cost" in analyze_metrics