from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.prompts import load_prompts
from app.core.tools import Tool
from app.features.documents.schemas import READ_DOCUMENTS_MAX, DocumentList, DocumentReading
from app.features.documents.service import DocumentService

PROMPTS = load_prompts(prompts_py=__file__)
SEARCH_MAX_LENGTH = 200


class ListDocumentsArgs(BaseModel):
    text: str | None = Field(
        default=None,
        min_length=1,
        max_length=SEARCH_MAX_LENGTH,
        description=PROMPTS["list_documents_text"],
    )


class ReadDocumentArgs(BaseModel):
    documents: list[Annotated[str, Field(min_length=1)]] = Field(
        min_length=1, max_length=READ_DOCUMENTS_MAX, description=PROMPTS["read_document_documents"]
    )
    question: str = Field(min_length=1, description=PROMPTS["read_document_question"])


def get_tools(service: DocumentService, owner_id: UUID) -> list[Tool[Any]]:
    async def list_documents(args: ListDocumentsArgs) -> DocumentList:
        listing = await service.list_summaries(owner_id=owner_id, text=args.text)
        if listing.left_out == 0:
            return listing
        note = PROMPTS["list_documents_left_out"].format(count=listing.left_out)
        return listing.model_copy(update={"note": note})

    async def read_document(args: ReadDocumentArgs) -> DocumentReading:
        return await service.read_documents(
            names=args.documents, question=args.question, owner_id=owner_id
        )

    return [
        Tool(
            name="list_documents",
            title="Look at your documents",
            icon="files",
            description=PROMPTS["list_documents"],
            args_schema=ListDocumentsArgs,
            handler=list_documents,
        ),
        Tool(
            name="read_document",
            title="Read your documents",
            icon="file-text",
            description=PROMPTS["read_document"],
            args_schema=ReadDocumentArgs,
            handler=read_document,
        ),
    ]
