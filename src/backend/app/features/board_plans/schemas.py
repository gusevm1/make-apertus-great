"""A customer's boards as the model plans them, before anything is stored.

`PlanAnswer` is what the model returns; `PlannedBoards` is what the server made of it after
every tile was validated and resolved against the banking API.
"""

from typing import Any

from pydantic import BaseModel, Field

from app.core.provenance import Check
from app.features.tiles.schemas import Template

TITLE_MAX = 60


class Signal(BaseModel):
    """A finding in the customer's data, computed by the server, with the tile that shows it."""

    id: str
    kind: str
    # One English sentence with the server's figures.
    text: str
    # Higher is more pressing; the hero comes from the strongest signals.
    strength: int
    template: Template | None = None
    args: dict[str, Any] | None = None


class CustomerDigest(BaseModel):
    # The compact text the model reads: facts and signals.
    text: str
    signals: list[Signal]


# --- what the model returns ---------------------------------------------------------------------


class TileChoice(BaseModel):
    signal: str | None = Field(
        default=None,
        description="The id of a signal whose ready-made tile to use, such as S3. "
        "Leave out when you give template and args yourself.",
    )
    template: Template | None = Field(
        default=None, description="A template of the catalogue. Leave out when you give a signal."
    )
    args: dict[str, Any] | None = Field(
        default=None,
        description="The template's arguments, with ids and names exactly as the data writes "
        "them. Leave out when you give a signal.",
    )
    title: str | None = Field(
        default=None,
        description="A short title in the customer's own terms, such as 'Child support for "
        "Lina'. No figures. Leave out to use the default title.",
    )


class BoardChoice(BaseModel):
    name: str = Field(description="The board's tab name, one to three words.")
    tiles: list[TileChoice] = Field(
        description="The tiles in order. The first tile of the first board is the hero."
    )


class IdeaChoice(BaseModel):
    title: str = Field(description="A further board the customer could want, a few words.")
    signal: str = Field(description="The id of the signal this idea is about, such as S5.")


class PlanAnswer(BaseModel):
    kind: str = Field(
        description="What kind of customer this is, in one short sentence, from the evidence."
    )
    evidence: list[str] = Field(
        description="Two to four signal ids or facts that show the kind, such as 'S1: ...'."
    )
    question: str = Field(
        description="The one question that matters most to this customer, in their words."
    )
    boards: list[BoardChoice]
    ideas: list[IdeaChoice] = Field(
        default_factory=list, description="Up to three further boards, each about one signal."
    )


# --- what the server returns ----------------------------------------------------------------


class PlannedTile(BaseModel):
    template: Template
    args: dict[str, Any]
    title: str


class PlannedBoard(BaseModel):
    name: str
    tiles: list[PlannedTile]


class Idea(BaseModel):
    title: str
    # The signal's sentence, so its figures are the server's.
    text: str


class DroppedTile(BaseModel):
    title: str
    reason: str


class PlannedBoards(BaseModel):
    kind: str
    evidence: list[str]
    question: str
    boards: list[PlannedBoard]
    ideas: list[Idea]
    dropped: list[DroppedTile]
    model: str
    latency_ms: int
    checks: list[Check]
