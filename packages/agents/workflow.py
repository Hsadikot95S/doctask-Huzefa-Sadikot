from langgraph.graph import END, StateGraph

from packages.core.state import WorkflowState

from typing import Any

def extract_text(state: WorkflowState) -> WorkflowState:
    state["extracted_text"] = "Dummy extracted text"
    state["current_stage"] = "extract_text"
    state["stages"]["extract_text"] = {
        "status": "completed",
        "error": None,
    }

    return state


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


def build_graph() -> Any:
    graph = StateGraph(WorkflowState)

    graph.add_node("extract_text", extract_text)
    graph.add_node("analyze", analyze)

    graph.set_entry_point("extract_text")
    graph.add_edge("extract_text", "analyze")
    graph.add_edge("analyze", END)

    return graph.compile()

def build_stage_graph(stage: str) -> Any:
    graph = StateGraph(WorkflowState)

    if stage == "extract_text":
        graph.add_node("extract_text", extract_text)
        graph.set_entry_point("extract_text")
        graph.add_edge("extract_text", END)

    elif stage == "analyze":
        graph.add_node("analyze", analyze)
        graph.set_entry_point("analyze")
        graph.add_edge("analyze", END)

    else:
        raise ValueError(f"Unsupported workflow stage: {stage}")

    return graph.compile()