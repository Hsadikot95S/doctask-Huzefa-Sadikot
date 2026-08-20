from fastapi import APIRouter, File, HTTPException, UploadFile, status

from apps.api.schemas.documents import DocumentUploadResponse
from packages.documents.application import DocumentApplicationService
from packages.db.database import SessionLocal


router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    file: UploadFile = File(...),
):
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded document is empty",
        )

    service = DocumentApplicationService()

    try:
        with SessionLocal() as session:
            document, _, run = (
                service.ingest_and_create_run(
                    session,
                    filename=file.filename,
                    content=content,
                )
            )

            return DocumentUploadResponse(
                document_id=document.id,
                run_id=run.id,
                filename=document.filename,
                status=run.status,
            )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc