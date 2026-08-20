from uuid import UUID
from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    document_id: UUID
    run_id: UUID
    filename: str
    status: str