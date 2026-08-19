from typing import Any, cast

from packages.core.state import WorkflowState


def invoke_workflow_graph(
    graph: Any,
    state: WorkflowState,
) -> WorkflowState:
    result = graph.invoke(state)
    return cast(WorkflowState, result)