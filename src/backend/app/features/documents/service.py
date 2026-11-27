from uuid import UUID

from app.clients.banking import BankingClient
from app.clients.ocr import OcrClient
from app.core.errors import BadRequestError, NotFoundError, PayloadTooLargeError
from app.features.documents.repository import DocumentRepository
from app.features.documents.schemas import (
    DOCUMENT_MAX_BYTES,
    DOCUMENT_TOO_LARGE_MESSAGE,
    NAME_MAX_LENGTH,
    Document,
)


class DocumentService:
    def __init__(
        self, documents: DocumentRepository, banking: BankingClient, ocr: OcrClient
    ) -> None:
        self.documents = documents
        self.banking = banking
        self.ocr = ocr

    async def create_document(
        self, content: bytes, name: str | None, content_type: str | None, owner_id: UUID, token: str
    ) -> Document:
        """Read the upload once with OCR, store it in the e-banking and keep its text."""
        if len(content) > DOCUMENT_MAX_BYTES:
            raise PayloadTooLargeError(DOCUMENT_TOO_LARGE_MESSAGE)
        if not content:
            raise BadRequestError("The document is empty.")
        if not name:
            # The OCR service picks its reader from the file extension.
            raise BadRequestError("The document needs a file name with its extension.")
        name = name[-NAME_MAX_LENGTH:]
        # OCR first: a file it cannot read then leaves nothing behind in the e-banking.
        markdown = await self.ocr.convert(content=content, filename=name)
        stored = await self.banking.upload_document(
            token=token, content=content, filename=name, content_type=content_type
        )
        return await self.documents.create(
            owner_id=owner_id, banking_document_id=stored["id"], name=name, markdown=markdown
        )

    async def list_documents(self, owner_id: UUID) -> list[Document]:
        """The customer's documents, newest first."""
        return await self.documents.list(owner_id=owner_id)

    async def get_documents(self, document_ids: list[UUID], owner_id: UUID) -> list[Document]:
        """The customer's documents in the given order; someone else's counts as not found."""
        if not document_ids:
            return []
        found = await self.documents.list_owned(document_ids=document_ids, owner_id=owner_id)
        by_id = {document.id: document for document in found}
        missing = [str(document_id) for document_id in document_ids if document_id not in by_id]
        if missing:
            raise NotFoundError(f"Document not found: {', '.join(missing)}")
        return [by_id[document_id] for document_id in dict.fromkeys(document_ids)]
