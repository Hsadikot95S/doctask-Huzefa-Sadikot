from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Document:
    document_id: str
    filename: str
    content_hash: str
    mime_type: str
    size_bytes: int
    created_at: datetime


@dataclass(frozen=True)
class DocumentPage:
    document_id: str
    page_number: int
    text: str


@dataclass(frozen=True)
class Evidence:
    document_id: str
    page_number: int
    text: str
    locator: Optional[str] = None
