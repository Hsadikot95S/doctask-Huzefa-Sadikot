from typing import Any

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from packages.core.state import WorkflowState

from packages.db.repositories.runs import RunRepository
from packages.db.repositories.documents import DocumentRepository
from packages.db.repositories.runs import RunRepository

from packages.documents.service import DocumentService

from uuid import UUID



def make_extract_text_node(
    session: Session,
    document_service: DocumentService,
):
    def extract_text(state: WorkflowState) -> WorkflowState:
        document, pages = document_service.ingest(
            session,
            state["document_path"], # type: ignore
        )

        if state.get('document_id') is None:

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

    elif stage == "incremental_extract_text":
        if session is None:
            raise ValueError(
                "A database session is required for incremental_extract_text"
            )

        graph.add_node(
            "incremental_extract_text",
            make_incremental_extract_text_node(session),
        )

        graph.set_entry_point("incremental_extract_text")
        graph.add_edge("incremental_extract_text", END)

    elif stage == "analyze":
        graph.add_node(
            "analyze",
            analyze,
        )

        graph.set_entry_point("analyze")
        graph.add_edge("analyze", END)

    elif stage == "incremental_analyze":
        if session is None:
            raise ValueError(
                "A database session is required for incremental_analyze"
            )

        graph.add_node(
            "incremental_analyze",
            lambda state: incremental_analyze(
                state, # pyright: ignore[reportArgumentType]
                session=session,
            ),
        )

        graph.set_entry_point("incremental_analyze")
        graph.add_edge("incremental_analyze", END)

    else:
        raise ValueError(
            f"Unsupported workflow stage: {stage}"
        )

    return graph.compile()

def make_incremental_extract_text_node(session: Session):
    def extract_text(state: WorkflowState) -> WorkflowState:
        document_id = UUID(state["document_id"])

        repository = DocumentRepository()

        document = repository.get(
            session,
            document_id,
        )

        if document is None:
            raise ValueError(
                f"Document {document_id} not found"
            )

        pages = repository.get_pages(
            session,
            document_id,
        )

        state["extracted_text"] = "\n".join(
            page.text
            for page in pages
        )

        # IMPORTANT:
        # Do not overwrite document_id.
        state["current_stage"] = "extract_text"

        state["stages"]["extract_text"] = {
            "status": "completed",
            "error": None,
        }

        return state

    return extract_text


def incremental_analyze(
    state: WorkflowState,
    *,
    session: Session,
) -> WorkflowState:
    if not state.get("target_run_id"):
        raise ValueError(
            "Incremental analysis requires target_run_id"
        )

    target_run = RunRepository().get(
        session,
        UUID(state["target_run_id"]),
    )

    if target_run is None:
        raise ValueError(
            f"Target run {state['target_run_id']} not found"
        )

    target_findings = target_run.state.get(
        "findings",
        [],
    )

    new_finding = {
        "finding_id": f"UPDATE-{state['run_id']}",
        "description": "Sample incremental finding",
        "status": "pending",
        "evidence": [
            f"document:{state['document_id']}"
        ],
    }

    state["findings"] = [ # pyright: ignore[reportGeneralTypeIssues]
        *target_findings,
        new_finding,
    ]

    state["current_stage"] = "analyze"
    state["stages"]["analyze"] = {
        "status": "completed",
        "error": None,
    }

    return state