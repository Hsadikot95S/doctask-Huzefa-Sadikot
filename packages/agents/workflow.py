from typing import Any

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from packages.core.state import WorkflowState
from packages.documents.service import DocumentService


def make_extract_text_node(
    session: Session,
    document_service: DocumentService,
):
    def extract_text(state: WorkflowState) -> WorkflowState:
        document, pages = document_service.ingest(
            session,
            state["document_path"],
        )

        state["document_id"] = document.document_id

        state["extracted_text"] = "\n".join(
            page.text
            for page in pages
        )

        state["current_stage"] = "extract_text"
        state["stages"]["extract_text"] = {
            "status": "completed",
            "error": None,
        }

        return state

    return extract_text


def analyze(state: WorkflowState) -> WorkflowState:
    state["findings"] = [
        {
            "finding_id": "F-001",
            "description": "Sample finding",
            "status": "pending",
            "evidence": ["sample.pdf:page=1"],
        }
    ]

    state["current_stage"] = "analyze"
    state["stages"]["analyze"] = {
        "status": "completed",
        "error": None,
    }

    return state


def build_graph(
    *,
    session: Session | None = None,
    document_service: DocumentService | None = None,
) -> Any:
    graph = StateGraph(WorkflowState)

    if session is None:
        raise ValueError(
            "A database session is required to build the workflow"
        )

    graph.add_node(
        "extract_text",
        make_extract_text_node(
            session,
            document_service or DocumentService(),
        ),
    )

    graph.add_node("analyze", analyze)

    graph.set_entry_point("extract_text")
    graph.add_edge("extract_text", "analyze")
    graph.add_edge("analyze", END)

    return graph.compile()


def build_stage_graph(
    stage: str,
    *,
    session: Session | None = None,
    document_service: DocumentService | None = None,
) -> Any:
    graph = StateGraph(WorkflowState)

    if stage == "extract_text":
        if session is None:
            raise ValueError(
                "A database session is required for extract_text"
            )

        graph.add_node(
            "extract_text",
            make_extract_text_node(
                session,
                document_service or DocumentService(),
            ),
        )

        graph.set_entry_point("extract_text")
        graph.add_edge("extract_text", END)

    elif stage == "analyze":
        graph.add_node("analyze", analyze)
        graph.set_entry_point("analyze")
        graph.add_edge("analyze", END)

    else:
        raise ValueError(
            f"Unsupported workflow stage: {stage}"
        )

    return graph.compile()