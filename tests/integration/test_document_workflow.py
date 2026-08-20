from pathlib import Path

from packages.agents.workflow import build_stage_graph
from packages.db.database import SessionLocal


def test_extract_text_stage_ingests_real_document(tmp_path: Path):
    path = tmp_path / "contract.txt"

    path.write_text(
        "Payment is due within 30 days.\n"
        "The agreement expires in 2027.",
        encoding="utf-8",
    )

    with SessionLocal() as session:
        graph = build_stage_graph(
            "extract_text",
            session=session,
        )

        state = {
            "run_id": "test-run",
            "document_path": str(path),
            "status": "running",
            "current_stage": "extract_text",
            "document_id": None,
            "extracted_text": None,
            "findings": [],
            "stages": {},
            "error": None,
        }

        result = graph.invoke(state)

        session.commit()

    assert result["document_id"] is not None
    assert (
        "Payment is due within 30 days."
        in result["extracted_text"]
    )
    assert (
        "The agreement expires in 2027."
        in result["extracted_text"]
    )
    assert (
        result["stages"]["extract_text"]["status"]
        == "completed"
    )