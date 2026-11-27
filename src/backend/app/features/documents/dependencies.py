from typing import Annotated
from uuid import UUID

from fastapi import Depends

from app.clients.apertus import ApertusClientDep
from app.clients.banking import BankingClientDep
from app.clients.ocr import OcrClientDep
from app.core.auth import CurrentUserDep
from app.core.db import SessionDep
from app.features.documents.repository import DocumentRepository
from app.features.documents.schemas import Document
from app.features.documents.service import DocumentService


def get_document_repo(session: SessionDep) -> DocumentRepository:
    return DocumentRepository(session=session)


def get_document_service(
    documents: Annotated[DocumentRepository, Depends(get_document_repo)],
    banking: BankingClientDep,
    ocr: OcrClientDep,
    apertus: ApertusClientDep,
) -> DocumentService:
    return DocumentService(documents=documents, banking=banking, ocr=ocr, apertus=apertus)


DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]


async def get_owned_document(
    document_id: UUID, user: CurrentUserDep, service: DocumentServiceDep
) -> Document:
    documents = await service.get_documents(document_ids=[document_id], owner_id=user.id)
    return documents[0]


OwnedDocumentDep = Annotated[Document, Depends(get_owned_document)]
