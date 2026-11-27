from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

DOCUMENT_MAX_BYTES = 10 * 1024 * 1024
DOCUMENT_TOO_LARGE_MESSAGE = "The document is larger than 10 MB. Send a smaller one."
NAME_MAX_LENGTH = 200


class Document(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    banking_document_id: str
    name: str
    markdown: str
    created_at: datetime


class ResponseDocument(BaseModel):
    id: UUID
    name: str
    created_at: datetime
