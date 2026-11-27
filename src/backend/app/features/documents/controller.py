from fastapi import APIRouter, Depends, UploadFile

from app.core.auth import CurrentUserDep, require_user
from app.core.uploads import size_limited_route
from app.features.documents.dependencies import DocumentServiceDep
from app.features.documents.schemas import (
    DOCUMENT_MAX_BYTES,
    DOCUMENT_TOO_LARGE_MESSAGE,
    Document,
    ResponseDocument,
)

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
    dependencies=[Depends(require_user)],
    route_class=size_limited_route(
        max_bytes=DOCUMENT_MAX_BYTES, message=DOCUMENT_TOO_LARGE_MESSAGE
    ),
)


def _document_response(document: Document) -> ResponseDocument:
    return ResponseDocument.model_validate(document, from_attributes=True)


@router.post("", response_model=ResponseDocument, status_code=201)
async def create_document(
    file: UploadFile, user: CurrentUserDep, service: DocumentServiceDep
) -> ResponseDocument:
    """Upload one document (PDF, scan, photo or Office file, at most 10 MB) and read its text."""
    # One byte over the limit is enough to know it is too large.
    content = await file.read(DOCUMENT_MAX_BYTES + 1)
    document = await service.create_document(
        content=content,
        name=file.filename,
        content_type=file.content_type,
        owner_id=user.id,
        token=user.token,
    )
    return _document_response(document=document)


@router.get("", response_model=list[ResponseDocument])
async def list_documents(
    user: CurrentUserDep, service: DocumentServiceDep
) -> list[ResponseDocument]:
    """List your documents, newest first."""
    documents = await service.list_documents(owner_id=user.id)
    return [_document_response(document=document) for document in documents]
