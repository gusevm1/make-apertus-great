import asyncio
import re
from datetime import date, timedelta
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import BadRequestError
from app.core.tools import Tool, TurnScope
from app.features.boards.prompts import (
    PROMPTS,
    board_context,
    board_guide,
    figures,
    payee_lines,
    payee_names,
)
from app.features.boards.schemas import (
    BOARD_ABOUT_MAX_LENGTH,
    BOARD_NAME_MAX_LENGTH,
    TILE_TITLE_MAX_LENGTH,
    Board,
    RequestBoardCreate,
    Tile,
)
from app.features.boards.service import BoardService
from app.features.tiles.meanings import meaning
from app.features.board_plans.schemas import Signal
from app.features.tiles.schemas import (
    AnyPayload,
    ExpectedIncomePayload,
    PaydayBalancePayload,
    Template,
)

MERCHANT_TEMPLATES = {"merchant_spending", "monthly_spending"}
MERCHANTS_MAX = 6
# Question words and the templates of the tiles that answer such a question, first match wins.
ANSWERING_TILES: list[tuple[re.Pattern[str], tuple[str, ...]]] = [
    (
        re.compile(r"payday|salary|last until|until (?:the )?(?:end|next)|zahltag|lohn|reicht", re.I),
        ("payday_balance", "bills_until_payday"),
    ),
]
# The answer about a new board names its first tiles only.
NEW_BOARD_TILES_TOLD = 2
TILE_INDEX = re.compile(r"T(\d+)", re.IGNORECASE)
WORD = re.compile(r"[^\W\d_]{3,}")
# Words of "the groceries tile" that name no tile.
NOT_NAMES = {"the", "tile", "tiles", "board", "card", "this", "that", "and", "for", "from", "with"}
QUOTES = "\"'“”„«»‹›"
MOVES: dict[str, str] = {
    "top": 'Moved "{title}" to the top',
    "up": 'Moved "{title}" up',
    "down": 'Moved "{title}" down',
    "bottom": 'Moved "{title}" to the bottom',
}


class Args(BaseModel):
    # An argument the tool does not have is an error the model can correct.
    model_config = ConfigDict(extra="forbid")


class AddTileArgs(BaseModel):
    # The template's own arguments sit beside these: nested one level deeper, Apertus dropped braces.
    model_config = ConfigDict(extra="allow")

    signal: str | None = Field(default=None, description=PROMPTS["add_tile_signal"])
    template: Template | None = Field(default=None, description=PROMPTS["add_tile_template"])
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=TILE_TITLE_MAX_LENGTH,
        description=PROMPTS["add_tile_title"],
    )


class ChangeTileArgs(BaseModel):
    # The template's arguments to change sit beside the tile, as with add_tile.
    model_config = ConfigDict(extra="allow")

    tile: str = Field(description=PROMPTS["tile_ref"])


class RenameTileArgs(Args):
    tile: str = Field(description=PROMPTS["tile_ref"])
    title: str = Field(
        min_length=1, max_length=TILE_TITLE_MAX_LENGTH, description=PROMPTS["rename_tile_title"]
    )


class MoveTileArgs(Args):
    tile: str = Field(description=PROMPTS["tile_ref"])
    to: Literal["top", "up", "down", "bottom"] = Field(description=PROMPTS["move_tile_to"])


class RemoveTileArgs(Args):
    tile: str = Field(description=PROMPTS["tile_ref"])


class RenameBoardArgs(Args):
    name: str = Field(
        min_length=1, max_length=BOARD_NAME_MAX_LENGTH, description=PROMPTS["rename_board_name"]
    )


class CreateBoardArgs(Args):
    about: str = Field(
        min_length=1, max_length=BOARD_ABOUT_MAX_LENGTH, description=PROMPTS["create_board_about"]
    )


class BoardTileFigures(BaseModel):
    title: str
    figure_chf: float


class BoardChange(BaseModel):
    """What a board tool did; the page prints `summary` under the answer."""

    summary: str
    # The board a call created, which the page offers to open.
    board_id: UUID | None = None
    # The server's sentence about what the tile shows, for a tile taken from a signal.
    finding: str | None = None
    # What the tile's figures mean, verdict included, in the server's words.
    meaning: str | None = None
    # A note for the customer's profile that this tile brings up, for propose_context_entry.
    suggested_note: str | None = None
    # The note itself, which the server proposes when the decision does not.
    suggested_note_text: str | None = None
    figures: dict[str, Any] | None = None
    tiles: list[BoardTileFigures] | None = None


async def get_turn(
    service: BoardService,
    board: Board,
    tile_id: UUID | None,
    owner_id: UUID,
    token: str,
    today: date,
    active_notes: list[str],
) -> TurnScope:
    """The open board for the chat: what its prompt shows and the tools that change it."""
    (resolved, dropped), customer = await asyncio.gather(
        service.get_board_resolved(board=board, token=token, today=today),
        service.planner.read_customer(token=token, today=today),
    )
    payloads: dict[UUID, AnyPayload | None] = {tile.id: payload for tile, payload in resolved}
    payloads.update({tile.id: None for tile, _ in dropped})
    ordered = sorted([*(tile for tile, _ in resolved), *(tile for tile, _ in dropped)], key=_position)
    # Indexes as the prompt shows them; a tile added in this turn gets the next one.
    indexes: list[UUID] = [tile.id for tile in ordered]
    signals = {signal.id: signal for signal in customer.signals}

    def label(tile_id: UUID) -> str:
        if tile_id not in indexes:
            indexes.append(tile_id)
        return f"T{indexes.index(tile_id) + 1}"

    on_board: dict[str, str] = {}
    for signal in customer.signals:
        same = next(
            (
                tile
                for tile in ordered
                if signal.template is not None
                and tile.template == signal.template
                and _same_args(first=tile.args, second=signal.args or {})
            ),
            None,
        )
        if same is not None:
            on_board[signal.id] = label(tile_id=same.id)
    saved = {note.casefold().strip() for note in active_notes}
    notes = [
        note
        for note in await _late_income_notes(
            service=service, signals=customer.signals, payloads=payloads, token=token, today=today
        )
        if note.casefold().strip() not in saved
    ]
    selected = next((tile for tile in ordered if tile.id == tile_id), None)
    selected_payload = None if selected is None else payloads[selected.id]
    context = board_context(
        name=board.name,
        tiles=[
            (label(tile_id=tile.id), tile, payloads[tile.id], _meaning(payload=payloads[tile.id], today=today))
            for tile in ordered
        ],
        selected=None
        if selected is None or selected_payload is None
        else (
            label(tile_id=selected.id),
            selected,
            selected_payload,
            meaning(payload=selected_payload, today=today),
        ),
        signals=customer.signals,
    )

    async def listing() -> str:
        tiles = await service.list_tiles(board_id=board.id)
        return ", ".join(f'{label(tile_id=tile.id)} "{tile.title}"' for tile in tiles) or "none"

    async def find(ref: str) -> Tile:
        tiles = await service.list_tiles(board_id=board.id)
        wanted = ref.strip().strip(QUOTES).strip()
        match = TILE_INDEX.fullmatch(wanted)
        if match is not None:
            number = int(match.group(1))
            if 0 < number <= len(indexes):
                found = next((tile for tile in tiles if tile.id == indexes[number - 1]), None)
                if found is not None:
                    return found
        exact = [tile for tile in tiles if tile.title.casefold() == wanted.casefold()]
        if len(exact) == 1:
            return exact[0]
        words = set(WORD.findall(wanted.casefold())) - NOT_NAMES
        scores = [(len(words & _words(tile=tile)), tile) for tile in tiles]
        best = max((score for score, _ in scores), default=0)
        matches = [tile for score, tile in scores if score == best]
        if best > 0 and len(matches) == 1:
            return matches[0]
        raise BadRequestError(PROMPTS["unknown_tile"].format(ref=ref, tiles=await listing()))

    async def add_tile(args: AddTileArgs) -> BoardChange:
        if args.signal is not None:
            signal = signals.get(args.signal.strip().upper())
            if signal is None or signal.template is None:
                ready = ", ".join(
                    item.id for item in customer.signals if item.template is not None
                )
                raise BadRequestError(
                    PROMPTS["unknown_signal"].format(ref=args.signal, signals=ready or "none")
                )
            template, tile_args = signal.template, signal.args or {}
            finding = signal.text
        elif args.template is not None:
            finding = None
            tile_args = dict(args.model_extra or {})
            nested = tile_args.get("args")
            # The model sometimes nests them as before; the meaning is the same.
            if set(tile_args) == {"args"} and isinstance(nested, dict):
                tile_args = nested
            template = args.template
        else:
            raise BadRequestError(PROMPTS["add_tile_needs"])
        tile_args = _known_merchants(template=template, args=tile_args, facts=customer.text)
        same = await service.find_same_tile(board_id=board.id, template=template, args=tile_args)
        if same is not None:
            payload = await service.resolve_tile(tile=same, token=token, today=today)
            return BoardChange(
                summary=f'"{same.title}" is on the board already',
                finding=finding,
                meaning=meaning(payload=payload, today=today),
                suggested_note=_suggested_note(payload=payload, notes=notes),
            suggested_note_text=None
            if _suggested_note(payload=payload, notes=notes) is None
            else notes[0],
                figures=figures(payload=payload),
            )
        try:
            tile, payload = await service.add_tile(
                board_id=board.id,
                template=template,
                args=tile_args,
                title=args.title,
                position=None,
                token=token,
                today=today,
            )
        except BadRequestError as error:
            raise with_payees(error=error, template=template) from error
        return BoardChange(
            summary=f'Added "{tile.title}"',
            finding=finding,
            meaning=meaning(payload=payload, today=today),
            suggested_note=_suggested_note(payload=payload, notes=notes),
            suggested_note_text=None
            if _suggested_note(payload=payload, notes=notes) is None
            else notes[0],
            figures=figures(payload=payload),
        )

    def with_payees(error: BadRequestError, template: str) -> BadRequestError:
        # A shop the bookings do not know: the customer's own payees to choose from instead.
        if template not in MERCHANT_TEMPLATES:
            return error
        payees = payee_lines(facts=customer.text)
        return BadRequestError(PROMPTS["unknown_merchants"].format(error=error, payees=payees))

    async def change_tile(args: ChangeTileArgs) -> BoardChange:
        tile = await find(ref=args.tile)
        changes = dict(args.model_extra or {})
        nested = changes.get("args")
        if set(changes) == {"args"} and isinstance(nested, dict):
            changes = nested
        if not changes:
            raise BadRequestError(PROMPTS["change_tile_needs"])
        # The new tile takes the old one's place and title, then the old one goes.
        try:
            changed, payload = await service.add_tile(
                board_id=board.id,
                template=tile.template,
                args={**tile.args, **changes},
                title=tile.title,
                position=tile.position,
                token=token,
                today=today,
            )
        except BadRequestError as error:
            raise with_payees(error=error, template=tile.template) from error
        await service.remove_tile(tile=tile)
        indexes[indexes.index(tile.id)] = changed.id
        return BoardChange(
            summary=f'Changed "{tile.title}"',
            meaning=meaning(payload=payload, today=today),
            figures=figures(payload=payload),
        )

    async def rename_tile(args: RenameTileArgs) -> BoardChange:
        tile = await find(ref=args.tile)
        await service.rename_tile(tile=tile, title=args.title)
        return BoardChange(summary=f'Renamed "{tile.title}" to "{args.title}"')

    async def move_tile(args: MoveTileArgs) -> BoardChange:
        tile = await find(ref=args.tile)
        tiles = await service.list_tiles(board_id=board.id)
        current = next(index for index, item in enumerate(tiles) if item.id == tile.id)
        target = {
            "top": 0,
            "up": max(current - 1, 0),
            "down": min(current + 1, len(tiles) - 1),
            "bottom": len(tiles) - 1,
        }[args.to]
        await service.move_tile(tile=tile, position=target)
        return BoardChange(
            summary=MOVES[args.to].format(title=tile.title)
        )

    async def remove_tile(args: RemoveTileArgs) -> BoardChange:
        tile = await find(ref=args.tile)
        await service.remove_tile(tile=tile)
        return BoardChange(summary=f'Removed "{tile.title}"')

    async def rename_board(args: RenameBoardArgs) -> BoardChange:
        renamed = await service.rename_board(board_id=board.id, name=args.name)
        return BoardChange(summary=f'Renamed the board to "{renamed.name}"')

    async def create_board(args: CreateBoardArgs) -> BoardChange:
        created = await service.create_board(
            owner_id=owner_id, data=RequestBoardCreate(about=args.about), token=token, today=today
        )
        filled, dropped = await service.get_board_resolved(board=created, token=token, today=today)
        starts = " ".join(
            PROMPTS["new_board_tile"].format(title=tile.title, meaning=meaning(payload=payload, today=today))
            for tile, payload in filled[:NEW_BOARD_TILES_TOLD]
        )
        plans = await service.list_board_plans(owner_id=owner_id)
        plan = next((item for item in plans if item.request == args.about.strip()), None)
        reasons = [reason for _, reason in dropped]
        reasons += [] if plan is None else [item.reason for item in plan.dropped]
        missing = " ".join(reasons)
        return BoardChange(
            summary=f'New board "{created.name}"',
            board_id=created.id,
            meaning=PROMPTS["new_board"].format(
                about=args.about, tiles=starts or PROMPTS["new_board_empty"], missing=missing
            ).strip(),
            tiles=[
                BoardTileFigures(title=tile.title, figure_chf=float(payload.figure_chf))
                for tile, payload in filled[:NEW_BOARD_TILES_TOLD]
            ],
        )

    tools: list[Tool[Any]] = [
        Tool(
            name="add_tile",
            title="Add a tile",
            icon="square-plus",
            description=PROMPTS["add_tile"],
            args_schema=AddTileArgs,
            handler=add_tile,
            pointer=_both_cases,
        ),
        Tool(
            name="change_tile",
            title="Change a tile",
            icon="sliders-horizontal",
            description=PROMPTS["change_tile"],
            args_schema=ChangeTileArgs,
            handler=change_tile,
        ),
        Tool(
            name="rename_tile",
            title="Rename a tile",
            icon="pencil",
            description=PROMPTS["rename_tile"],
            args_schema=RenameTileArgs,
            handler=rename_tile,
        ),
        Tool(
            name="move_tile",
            title="Move a tile",
            icon="move",
            description=PROMPTS["move_tile"],
            args_schema=MoveTileArgs,
            handler=move_tile,
        ),
        Tool(
            name="remove_tile",
            title="Remove a tile",
            icon="trash-2",
            description=PROMPTS["remove_tile"],
            args_schema=RemoveTileArgs,
            handler=remove_tile,
        ),
        Tool(
            name="rename_board",
            title="Rename the board",
            icon="pencil",
            description=PROMPTS["rename_board"],
            args_schema=RenameBoardArgs,
            handler=rename_board,
        ),
        Tool(
            name="create_board",
            title="Create a board",
            icon="layout-dashboard",
            description=PROMPTS["create_board"],
            args_schema=CreateBoardArgs,
            handler=create_board,
        ),
    ]
    def fallback(question: str) -> list[tuple[str, dict[str, Any]]]:
        """For a question its ready tiles answer: add them, so their meanings reach the answer."""
        if selected is not None:
            return []
        for words, templates in ANSWERING_TILES:
            if words.search(question) is None:
                continue
            requests: list[tuple[str, dict[str, Any]]] = []
            for template in templates:
                signal = next((item for item in customer.signals if item.template == template), None)
                if signal is not None:
                    requests.append(("add_tile", {"signal": signal.id}))
            if requests and notes and "payday_balance" in templates:
                requests.append(("propose_context_entry", {"kind": "fact", "text": notes[0]}))
            return requests
        return []

    return TurnScope(
        context=context,
        guide=board_guide(
            signals=customer.signals,
            labels=on_board,
            notes=notes,
            saved=active_notes,
            payees=payee_lines(facts=customer.text),
        ),
        tools=tools,
        fallback=fallback,
    )


async def _late_income_notes(
    service: BoardService,
    signals: list[Signal],
    payloads: dict[UUID, AnyPayload | None],
    token: str,
    today: date,
) -> list[str]:
    """A note worth proposing for each regular income that came late before and is open now."""
    labels = {
        payload.alternative.counterparty: payload.alternative.label
        for payload in payloads.values()
        if isinstance(payload, PaydayBalancePayload) and payload.alternative is not None
    }
    incomes = [
        signal.args["counterparty"]
        for signal in signals
        if signal.template == "expected_income" and signal.args is not None
    ]
    resolved = await asyncio.gather(
        *(
            service.tile_service.resolve(
                template="expected_income",
                args={"counterparty": counterparty},
                token=token,
                today=today,
            )
            for counterparty in incomes
        ),
        return_exceptions=True,
    )
    notes = []
    for payload in resolved:
        if not isinstance(payload, ExpectedIncomePayload) or payload.status != "not_arrived":
            continue
        late = [item for item in payload.months if item.state == "late" and item.arrived_on]
        if not late or late[-1].arrived_on is None:
            continue
        arrived = late[-1].arrived_on
        last_month = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        when = "last month" if late[-1].month == last_month else "last time"
        label = labels.get(payload.counterparty) or f"the income from {payload.counterparty}"
        notes.append(
            PROMPTS["late_income_note"].format(
                income=label[:1].upper() + label[1:],
                day=f"{arrived.day:02d}.{arrived.month:02d}.",
                when=when,
            )
        )
    return notes


def _meaning(payload: AnyPayload | None, today: date) -> str:
    return "" if payload is None else meaning(payload=payload, today=today)


def _known_merchants(template: str, args: dict[str, Any], facts: str) -> dict[str, Any]:
    """A kind of spending keeps only the shops among the customer's payees of its period."""
    merchants = args.get("merchants")
    # ponytail: two or fewer are shops the customer named, kept as they are; a third heuristic
    # would need the message itself
    if template not in MERCHANT_TEMPLATES or not isinstance(merchants, list) or len(merchants) <= 2:
        return args
    period = args.get("period", "this_month") if template == "merchant_spending" else "last_3_months"
    known = payee_names(facts=facts, period=period)
    kept = [name for name in merchants if str(name).casefold() in known]
    return args if not kept else {**args, "merchants": kept[:MERCHANTS_MAX]}


def _suggested_note(payload: AnyPayload, notes: list[str]) -> str | None:
    # ponytail: notes are only about late incomes, so they belong to the tiles that show one
    if not notes or payload.template not in {"payday_balance", "expected_income"}:
        return None
    return PROMPTS["suggested_note"].format(note=notes[0])


def _both_cases(result: dict[str, Any], answer: str) -> str | None:
    """The line under the answer when a tile with two cases is on the board."""
    if (result.get("figures") or {}).get("alternative") is None:
        return None
    is_added = result["summary"].startswith("Added")
    return PROMPTS["both_cases_added" if is_added else "both_cases_there"]


def _position(tile: Tile) -> int:
    return tile.position


def _words(tile: Tile) -> set[str]:
    return set(WORD.findall(f"{tile.title} {tile.template.replace('_', ' ')}".casefold()))


def _same_args(first: dict[str, Any], second: dict[str, Any]) -> bool:
    def present(args: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in args.items() if value is not None}

    return present(args=first) == present(args=second)
