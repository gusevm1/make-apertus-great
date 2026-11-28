from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.provenance import Provenance

Role = Literal["user", "assistant"]
TITLE_MAX_LENGTH = 200
MESSAGE_MAX_LENGTH = 4000
QUOTE_COMMENT_MAX_LENGTH = 1000
PAGE_TEXT_MAX_LENGTH = 200
DOCUMENTS_PER_MESSAGE_MAX = 3
QUOTES_PER_MESSAGE_MAX = 5


class Conversation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    title: str | None
    created_at: datetime


class RequestConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=TITLE_MAX_LENGTH)


class RequestConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=TITLE_MAX_LENGTH)


class ResponseConversation(BaseModel):
    id: UUID
    title: str | None
    created_at: datetime


class Quote(BaseModel):
    message_id: UUID
    text: str = Field(min_length=1, max_length=MESSAGE_MAX_LENGTH)
    comment: str | None = Field(default=None, max_length=QUOTE_COMMENT_MAX_LENGTH)


class MessageDocument(BaseModel):
    id: UUID
    name: str


class PageContext(BaseModel):
    title: str = Field(min_length=1, max_length=PAGE_TEXT_MAX_LENGTH)
    account_name: str | None = Field(default=None, max_length=PAGE_TEXT_MAX_LENGTH)


class Message(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    role: Role
    content: str
    provenance: Provenance | None
    quotes: list[Quote]
    documents: list[MessageDocument]
    created_at: datetime


class RequestMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=MESSAGE_MAX_LENGTH)
    quotes: list[Quote] = Field(default=[], max_length=QUOTES_PER_MESSAGE_MAX)
    document_ids: list[UUID] = Field(default=[], max_length=DOCUMENTS_PER_MESSAGE_MAX)
    page: PageContext | None = None
    # The customer's board open beside the chat, and the tile they asked about.
    board_id: UUID | None = None
    tile_id: UUID | None = None


class ResponseMessage(BaseModel):
    id: UUID
    conversation_id: UUID
    role: Role
    content: str
    provenance: Provenance | None
    quotes: list[Quote]
    documents: list[MessageDocument]
    created_at: datetime
