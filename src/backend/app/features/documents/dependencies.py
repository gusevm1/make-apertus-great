from typing import Annotated

from fastapi import Depends

from app.clients.apertus import ApertusClientDep
from app.clients.banking import BankingClientDep
from app.clients.ocr import OcrClientDep
from app.core.db import SessionDep
from app.features.documents.repository import DocumentRepository
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
