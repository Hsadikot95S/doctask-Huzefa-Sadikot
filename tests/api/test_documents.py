from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app


FIXTURE_DOCUMENT = (
    Path(__file__).parents[1]
    / "fixtures"
    / "documents"
    / "contract.pdf"
)


client = TestClient(app)


def test_upload_document_creates_document_and_run():
    content = FIXTURE_DOCUMENT.read_bytes()

    response = client.post(
        "/documents",
        files={
            "file": (
                "contract.pdf",
                content,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 202

    body = response.json()

    assert body["document_id"]
    assert body["run_id"]
    assert body["filename"] == "contract.pdf"
    assert body["status"] == "pending"