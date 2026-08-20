from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FindingResponse(BaseModel):
    finding_id: str
    description: str
    status: str
    evidence: list[str]


class StageResponse(BaseModel):
    status: str
    error: str | None


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: UUID
    document_path: str
    status: str
    current_stage: str
    error: str | None
    findings: list[FindingResponse]
    stages: dict[str, StageResponse]