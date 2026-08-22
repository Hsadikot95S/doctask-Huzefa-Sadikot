from typing import List, Literal, Optional, TypedDict


StageName = Literal[
    "extract_text",
    "analyze",
    "review",
    "complete",
    "failed",
]

RunStatus = Literal[
    "pending",
    "running",
    "awaiting_review",
    "completed",
    "failed",
]

FindingStatus = Literal[
    "pending",
    "approved",
    "rejected",
]


class Finding(TypedDict):
    finding_id: str
    description: str
    status: FindingStatus
    evidence: List[str]


class StageResult(TypedDict):
    status: Literal["pending", "running", "completed", "failed"]
    error: Optional[str]


class WorkflowState(TypedDict):
    # Identity
    run_id: str
    document_path: str

    status: RunStatus
    current_stage: StageName

    # Update context
    update_id: Optional[str]
    target_run_id: Optional[str]

    # Document processing
    document_id: Optional[str]
    extracted_text: Optional[str]

    # Analysis
    findings: List[Finding]

    # Stage-level execution state
    stages: dict[str, StageResult]

    # Error handling
    error: Optional[str]