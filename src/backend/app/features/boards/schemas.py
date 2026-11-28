from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.provenance import Check
from app.features.tiles.schemas import AnyPayload

BOARD_NAME_MAX_LENGTH = 80
BOARD_ABOUT_MAX_LENGTH = 500
TILE_TITLE_MAX_LENGTH = 80
DEFAULT_BOARD_NAME = "New board"
ABOUT_NAME_WORDS = 6


class Board(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    name: str
    position: int
    conversation_id: UUID | None
    created_at: datetime


class BoardSummary(BaseModel):
    board: Board
    tile_count: int


class Tile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    board_id: UUID
    template: str
    args: dict[str, Any]
    title: str
    position: int
    created_at: datetime


class Idea(BaseModel):
    title: str
    text: str


class DroppedIdea(BaseModel):
    title: str
    reason: str


class BoardPlan(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    request: str | None
    kind: str
    evidence: list[str]
    question: str
    ideas: list[Idea]
    dropped: list[DroppedIdea]
    model: str | None
    latency_ms: int
    checks: list[Check]
    created_at: datetime


class RequestBoardCreate(BaseModel):
    name: str | None = Field(default=None, max_length=BOARD_NAME_MAX_LENGTH)
    about: str | None = Field(default=None, max_length=BOARD_ABOUT_MAX_LENGTH)


class RequestBoardUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=BOARD_NAME_MAX_LENGTH)
    position: int | None = Field(default=None, ge=0)


class RequestTileCreate(BaseModel):
    template: str
    args: dict[str, Any]
    title: str | None = Field(default=None, min_length=1, max_length=TILE_TITLE_MAX_LENGTH)
    position: int | None = Field(default=None, ge=0)


class RequestTileUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=TILE_TITLE_MAX_LENGTH)
    position: int | None = Field(default=None, ge=0)


class ResponseBoardSummary(BaseModel):
    id: UUID
    name: str
    position: int
    conversation_id: UUID | None
    tile_count: int


class ResponseTile(BaseModel):
    id: UUID
    template: str
    title: str
    args: dict[str, Any]
    position: int
    payload: AnyPayload


class ResponseDroppedTile(BaseModel):
    tile_id: UUID
    title: str
    reason: str


class ResponseBoard(BaseModel):
    id: UUID
    name: str
    position: int
    conversation_id: UUID | None
    tiles: list[ResponseTile]
    dropped: list[ResponseDroppedTile]


class ResponseBoardPlan(BaseModel):
    id: UUID
    request: str | None
    kind: str
    evidence: list[str]
    question: str
    ideas: list[Idea]
    dropped: list[DroppedIdea]
    model: str | None
    latency_ms: int
    checks: list[Check]
    created_at: datetime
    # The boards this plan built; empty in the list of plans.
    boards: list[ResponseBoardSummary] = []
