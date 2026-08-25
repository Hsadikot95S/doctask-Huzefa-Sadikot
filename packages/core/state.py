from typing import List, Literal, Optional, TypedDict


StageName = Literal[
    "extract_text",
    "analyze",
    "review",
    "incremental_extract_text",
    "incremental_analyze",
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


class StageMetrics(TypedDict):
    duration_ms: float
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    estimated_cost: Optional[float]


class StageResult(TypedDict):
    status: Literal[
        "pending",
        "running",
        "completed",
        "failed",
    ]
    error: Optional[str]
    metrics: Optional[StageMetrics]


class ModelUsage(TypedDict):
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    estimated_cost: Optional[float]


class Evidence(TypedDict):
    document_id: str
    page_number: int
    text: str


class AnalysisResult(TypedDict):
    findings: List[Finding]
    usage: ModelUsage


class WorkflowState(TypedDict):
    # Identity
    run_id: str
    document_path: str

    # Document identity / lineage
    document_id: Optional[str]
    update_id: Optional[str]
    target_run_id: Optional[str]

    # Run lifecycle
    status: RunStatus
    current_stage: StageName

    # Document processing
    extracted_text: Optional[str]
    evidence: List[Evidence]

    # Analysis
    findings: List[Finding]
    analysis_usage: Optional[ModelUsage]

    # Stage-level execution state
    stages: dict[str, StageResult]

    # Error handling
    error: Optional[str]