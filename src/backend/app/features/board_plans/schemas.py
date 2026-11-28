"""A customer's boards as the model plans them, before anything is stored.

`PlanAnswer` is what the model returns; `PlannedBoards` is what the server made of it after
every tile was validated and resolved against the banking API.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, create_model

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
    # Every payee, account id and payment id the customer's data names, for an own tile.
    names: list[str] = []


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
    title: str | None = Field(description="A further board the customer could want, a few words.")
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
    # What the board cannot show, said once, such as what is left of a private loan.
    notes: list["DroppedTile"] = []


# --- the split calls, each with a schema built for this customer --------------------------------

OWN_TILE = "own tile"
# The templates a tile of the model's own may use, where knowing the world is the point.
OWN_TEMPLATES = ("merchant_spending", "regular_payments", "account_balances", "bill")
Period = Literal["this_month", "last_month", "last_3_months"]


def _enum(values: list[str]) -> Any:
    return Literal[tuple(values)]  # type: ignore[valid-type]


def _enum_list(values: list[str]) -> Any:
    return list[_enum(values)]  # type: ignore[valid-type]


def profile_schema(labels: list[str], heroes: list[str], late_income: bool) -> type[BaseModel]:
    """kind, evidence, question, hero and its title; evidence and hero only from these labels."""
    return create_model(
        "CustomerProfile",
        hero=(_enum(heroes), ...),
        kind=(str, ...),
        evidence=(_enum_list(labels), Field(min_length=1, max_length=4)),
        question=(str, ...),
        hero_title=(str, ...),
        # Asked for only when the hero can be a payday with money that has not arrived.
        expected_label=(str, ...) if late_income else (None, None),
    )


def board_schema(
    labels: list[str], names: list[str], first: list[str] | None, second: bool
) -> type[BaseModel]:
    """One verdict and title per signal of `labels`, so none repeats, plus up to two own tiles."""
    places = ["main", "second", "idea", "no"] if second else ["answers", "related", "unrelated"]
    verdict = create_model("SignalUse", use=(_enum(places), ...), title=(str, ...))
    own_fields: dict[str, Any] = {
        "template": (_enum(list(OWN_TEMPLATES)), ...),
        "names": (_enum_list(names), Field(min_length=1, max_length=8)),
        "period": (Period | None, None),
        "title": (str, ...),
    }
    if second:
        own_fields["board"] = (Literal["main", "second"], "main")
    own = create_model("OwnTile", **own_fields)
    use_fields: dict[str, Any] = {
        f"s{index}": (verdict, Field(alias=label)) for index, label in enumerate(labels)
    }
    uses = create_model("SignalUses", **use_fields)
    fields: dict[str, Any] = {}
    if first is not None:
        fields["first"] = (_enum([*first, OWN_TILE]), ...)
    fields["signals"] = (uses, ...)
    # A requested board is mostly the model's knowledge of the world: at least one own tile.
    fewest_own = 0 if first is None else 1
    fields["own"] = (list[own], Field(min_length=fewest_own, max_length=2))
    fields["name"] = (str, ...)
    if second:
        fields["second_name"] = (str | None, None)
    return create_model("BoardAnswer", **fields)


class EntryCheck(BaseModel):
    """One picked entry checked on its own: what it is, then whether it is about the request."""

    what: str = Field(max_length=80)
    about: Literal["yes", "no"]


class RequestKeywords(BaseModel):
    """What a request is about, as words the server looks for in the customer's data."""

    # Payee names picked from the customer's own lists; an enum in the schema sent to the model.
    entries: list[str] = []
    keywords: list[str] = Field(max_length=12)
    costs_only: bool
    open_bills: bool
    name: str
    goal_title: str | None = None
    payees_title: str | None = None
    spending_title: str | None = None


def request_schema(entries: list[str]) -> type[RequestKeywords]:
    """RequestKeywords with `entries` limited to this customer's payee names."""
    if not entries:
        return RequestKeywords
    return create_model(
        "RequestSelection",
        __base__=RequestKeywords,
        entries=(_enum_list(entries), Field(default_factory=list, max_length=8)),
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


class TraceItem(BaseModel):
    label: str
    text: str
    # How the page marks the line: a tile that was kept, one that was dropped, or neither.
    mark: Literal["kept", "dropped"] | None = None


class TraceStep(BaseModel):
    """One step of building a board, as the page shows it: who did it, how long, what came out."""

    name: str
    title: str
    actor: Literal["server", "apertus"]
    # What the step works from, such as the endpoints read or what the model was given.
    reads: str
    is_done: bool = False
    has_failed: bool = False
    seconds: float | None = None
    summary: str | None = None
    items: list[TraceItem] = []


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
    trace: list[TraceStep] = []


PlanAnswer.model_rebuild()
