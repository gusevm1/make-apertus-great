import asyncio
import calendar
import re
from datetime import date
from typing import Any

from app.clients.apertus import ApertusClient, Model
from app.core.errors import AppError
from app.core.provenance import Check
from app.features.board_plans import digest
from app.features.board_plans.digest import HERO_TEMPLATES, HERO_TOP, Raw, tile_key
from app.features.board_plans.prompts import plan_prompt
from app.features.board_plans.schemas import (
    TITLE_MAX,
    CustomerDigest,
    DroppedTile,
    Idea,
    PlanAnswer,
    PlannedBoard,
    PlannedBoards,
    PlannedTile,
    Signal,
    TileChoice,
)
from app.features.figure_checks.service import FigureCheckService
from app.features.ledger.service import LedgerService
from app.features.recurring_payments.service import RecurringPaymentService
from app.features.tiles.schemas import (
    AnyPayload,
    BillPayload,
    BillsUntilPaydayPayload,
    CardBillPayload,
    DueSoonPayload,
    MerchantSpendingPayload,
    NetWorthPayload,
    RegularPaymentsPayload,
)
from app.features.tiles.service import TileError, TileService

# Under Vercel's 120 s for a forwarded request.
PLAN_TIMEOUT_SECONDS = 110
MAIN_MIN, MAIN_MAX = 5, 7
SIDE_MIN, SIDE_MAX = 3, 5
REQUEST_MIN, REQUEST_MAX = 3, 6
FIRST_BOARDS_MAX = 2
IDEAS_MAX = 3
# The list argument of a template; a name in it that does not resolve is left out.
LIST_ARGS = {
    "merchant_spending": "merchants",
    "monthly_spending": "merchants",
    "regular_payments": "payees",
    "account_balances": "account_ids",
}
# A tile narrowed to fewer names than this keeps no title written for more.
NARROWED_KEPT_TITLE = 2


REPEATS_PAYMENTS = "shows the same payments as another tile on the board"
NET_WORTH_ALONE = "net worth of the accounts alone"
# Dropped by design, not because the model sent something wrong.
PAYDAY_NOT_TIGHT = "the day before payday is not tight for this customer"
EXPECTED_DROPS = {"board is full", REPEATS_PAYMENTS, NET_WORTH_ALONE, PAYDAY_NOT_TIGHT}
# Share of a payment list's rows that another list on the board may also show.
OVERLAP_SHARE = 0.5
# A single bill may stand beside the list it is in, to show its detail (a reminder, a fee).
SINGLE_BILL_BESIDE_LIST = {
    frozenset({"bill", "bills_until_payday"}),
    frozenset({"bill", "due_soon"}),
}
MONTH_NUMBERS = {calendar.month_name[number]: number for number in range(1, 13)}
# Fewer non-zero parts than this, and net worth only repeats the account balances.
NET_WORTH_PARTS_MIN = 2


class _Tile:
    def __init__(self, template: str, args: dict[str, Any], title: str, payload: AnyPayload):
        self.template = template
        self.args = args
        self.title = title
        self.payload = payload

    @property
    def key(self) -> str:
        return tile_key(self.template, self.args)


class BoardPlanService:
    def __init__(
        self,
        apertus: ApertusClient,
        tiles: TileService,
        ledger: LedgerService,
        recurring: RecurringPaymentService,
        figure_checks: FigureCheckService,
    ) -> None:
        self.apertus = apertus
        self.tiles = tiles
        self.ledger = ledger
        self.recurring = recurring
        self.figure_checks = figure_checks

    async def read_customer(self, token: str, today: date) -> CustomerDigest:
        """The customer's facts and the signals in them, computed without the model."""
        raw = await self._read_raw(token=token, today=today)
        resolved = await self._resolve_all(
            tiles=digest.candidates(raw=raw), token=token, today=today
        )
        signals = digest.signals(raw=raw, resolved=resolved)
        for signal in signals:
            if signal.template is not None and signal.args is not None:
                # The same shape as a validated tile, so the two compare.
                signal.args = self.tiles.validate_args(signal.template, signal.args).model_dump(
                    mode="json"
                )
        return CustomerDigest(text=digest.facts_text(raw=raw), signals=signals)

    async def plan_boards(
        self,
        token: str,
        today: date,
        request: str | None = None,
        existing: list[str] | None = None,
    ) -> PlannedBoards:
        """The customer's first boards, or one board for `request`, validated and ready to store."""
        customer = await self.read_customer(token=token, today=today)
        result = await self.apertus.structured(
            plan_prompt(
                facts=customer.text,
                signals=digest.signals_text(signals=customer.signals),
                request=request,
                existing=existing,
            ),
            schema=PlanAnswer,
            model=Model.SMART,
            purpose="board_plan",
            timeout_seconds=PLAN_TIMEOUT_SECONDS,
        )
        answer = result.content
        signals = {signal.id: signal for signal in customer.signals}
        tight = any(signal.kind == "payday_tight" for signal in customer.signals)
        dropped: list[DroppedTile] = []
        checks: list[Check] = []
        retitled: list[str] = []
        used: set[str] = set()
        limits = (
            [(REQUEST_MIN, REQUEST_MAX)]
            if request is not None
            else [(MAIN_MIN, MAIN_MAX), (SIDE_MIN, SIDE_MAX)][:FIRST_BOARDS_MAX]
        )
        boards: list[tuple[str, list[_Tile]]] = []
        requested = sum(len(board.tiles) for board in answer.boards[: len(limits)])
        for choice, (_, most) in zip(answer.boards, limits, strict=False):
            board_tiles: list[_Tile] = []
            for tile_choice in choice.tiles:
                tile = await self._validated(
                    choice=tile_choice, signals=signals, token=token, today=today, dropped=dropped
                )
                if tile is None:
                    continue
                if tile.key in used:
                    dropped.append(DroppedTile(title=tile.title, reason="repeats another tile"))
                    continue
                if request is None and tile.template == "payday_balance" and not tight:
                    dropped.append(DroppedTile(title=tile.title, reason=PAYDAY_NOT_TIGHT))
                    continue
                if len(board_tiles) == most:
                    dropped.append(DroppedTile(title=tile.title, reason="board is full"))
                    continue
                retitled += self._check_title(tile=tile)
                used.add(tile.key)
                board_tiles.append(tile)
            for tile in _repeating(tiles=board_tiles):
                board_tiles.remove(tile)
                dropped.append(DroppedTile(title=tile.title, reason=REPEATS_PAYMENTS))
            boards.append((choice.name.strip(), board_tiles))
        if not boards:
            boards.append(("Overview" if request is None else request[:TITLE_MAX], []))

        hero_detail = None
        if request is None:
            hero_detail = await self._ensure_hero(
                tiles=boards[0][1], signals=customer.signals, used=used, token=token, today=today
            )
        # A thin second board is left out rather than filled with tiles off its theme.
        boards = [board for index, board in enumerate(boards) if index == 0 or len(board[1]) >= SIDE_MIN]
        repaired = []
        for (name, board_tiles), (fewest, most) in zip(boards[:1], limits, strict=False):
            added = await self._repair(
                tiles=board_tiles,
                fewest=fewest,
                most=most,
                signals=customer.signals,
                used=used,
                token=token,
                today=today,
            )
            if added:
                repaired.append(f"{name}: {added} added")

        failed = [d for d in dropped if d.reason not in EXPECTED_DROPS]
        resolved_count = requested - len(failed)
        checks.append(
            Check(
                name="tiles_resolved",
                passed=not failed,
                detail=f"{resolved_count} of {requested} resolved"
                + ("" if not dropped else "; dropped: " + "; ".join(d.title for d in dropped)),
            )
        )
        checks.append(
            Check(
                name="titles_checked",
                passed=not retitled,
                detail=None if not retitled else "default title for: " + "; ".join(retitled),
            )
        )
        if request is None:
            checks.append(Check(name="hero", passed=hero_detail is None, detail=hero_detail))
        checks.append(
            Check(name="boards_full", passed=not repaired, detail="; ".join(repaired) or None)
        )
        taken = {name.casefold() for name in existing or []}
        repeated = [name for name, _ in boards if name.casefold() in taken]
        checks.append(
            Check(
                name="names_new",
                passed=not repeated,
                detail=None if not repeated else "already exists: " + ", ".join(repeated),
            )
        )
        ideas = [
            Idea(title=idea.title, text=signals[idea.signal].text)
            for idea in answer.ideas
            if idea.signal in signals and not self._signal_used(signals[idea.signal], used)
        ][:IDEAS_MAX]
        return PlannedBoards(
            kind=answer.kind,
            evidence=answer.evidence,
            question=answer.question,
            boards=[
                PlannedBoard(
                    name=name,
                    tiles=[
                        PlannedTile(template=t.template, args=t.args, title=t.title)  # type: ignore[arg-type]
                        for t in board_tiles
                    ],
                )
                for name, board_tiles in boards
            ],
            ideas=ideas,
            dropped=dropped,
            model=result.model,
            latency_ms=result.latency_ms,
            checks=checks,
        )

    async def _read_raw(self, token: str, today: date) -> Raw:
        rows = await self.ledger.list_rows(token=token)
        customer, accounts, upcoming, loans, portfolio, cards, recurring = await asyncio.gather(
            self.ledger.read(path="/customer", token=token),
            self.ledger.read(path="/accounts", token=token),
            self.ledger.read(path="/upcoming-payments", token=token),
            self.ledger.read(path="/loans", token=token),
            self.ledger.read(path="/portfolio", token=token),
            self.ledger.read(path="/cards", token=token),
            self.recurring.list_recurring(token=token, today=today),
        )
        return Raw(
            today=today,
            customer=customer,
            accounts=accounts["items"],
            upcoming=upcoming["items"],
            loans=loans["items"],
            portfolio=portfolio,
            cards=cards["items"],
            rows=rows,
            recurring=recurring,
        )

    async def _resolve_all(
        self, tiles: list[tuple[str, dict[str, Any]]], token: str, today: date
    ) -> dict[str, AnyPayload]:
        async def one(template: str, args: dict[str, Any]) -> AnyPayload | None:
            try:
                return await self.tiles.resolve(template, args, token, today)
            except (TileError, AppError):
                return None

        payloads = await asyncio.gather(*(one(template, args) for template, args in tiles))
        return {
            tile_key(template, args): payload
            for (template, args), payload in zip(tiles, payloads, strict=True)
            if payload is not None
        }

    async def _validated(
        self,
        choice: TileChoice,
        signals: dict[str, Signal],
        token: str,
        today: date,
        dropped: list[DroppedTile],
    ) -> _Tile | None:
        label = choice.title or choice.signal or choice.template or "a tile"
        if choice.signal is not None:
            signal = signals.get(choice.signal)
            if signal is None or signal.template is None or signal.args is None:
                dropped.append(DroppedTile(title=label, reason=f"no tile for {choice.signal}"))
                return None
            template, args = signal.template, signal.args
        elif choice.template is not None:
            template, args = choice.template, choice.args or {}
        else:
            dropped.append(DroppedTile(title=label, reason="neither a signal nor a template"))
            return None
        try:
            normalised = self.tiles.validate_args(template, args).model_dump(mode="json")
            payload = await self.tiles.resolve(template, normalised, token, today)
        except (TileError, AppError) as exc:
            narrowed = await self._narrowed(
                template=template, args=args, token=token, today=today
            )
            if narrowed is None:
                dropped.append(DroppedTile(title=label, reason=str(exc)))
                return None
            normalised, payload = narrowed
        if isinstance(payload, NetWorthPayload) and (
            len([part for part in payload.parts if part.value_chf > 0]) < NET_WORTH_PARTS_MIN
        ):
            dropped.append(DroppedTile(title=label, reason=NET_WORTH_ALONE))
            return None
        title = (choice.title or "").strip() or self.tiles.default_title(payload)
        if isinstance(payload, MerchantSpendingPayload) and len(payload.rows) < len(
            normalised["merchants"]
        ):
            normalised = {**normalised, "merchants": [row.merchant for row in payload.rows]}
            payload = await self.tiles.resolve(template, normalised, token, today)
        listed = LIST_ARGS.get(template)
        kept = None if listed is None else normalised[listed]
        if kept is not None and len(kept) < len(args.get(listed) or []):
            # Fewer names than the title was written for: it would promise the missing ones.
            if len(kept) < NARROWED_KEPT_TITLE:
                title = self.tiles.default_title(payload)
        return _Tile(template=template, args=normalised, title=title, payload=payload)

    async def _narrowed(
        self, template: str, args: dict[str, Any], token: str, today: date
    ) -> tuple[dict[str, Any], AnyPayload] | None:
        """The tile with only the names of its list that resolve on their own, if any do."""
        listed = LIST_ARGS.get(template)
        names = args.get(listed) if listed is not None else None
        if listed is None or not isinstance(names, list) or len(names) < 2:
            return None
        kept = []
        for name in names:
            try:
                alone = self.tiles.validate_args(template, {**args, listed: [name]})
                await self.tiles.resolve(template, alone.model_dump(mode="json"), token, today)
            except (TileError, AppError):
                continue
            kept.append(name)
        if not kept:
            return None
        try:
            normalised = self.tiles.validate_args(template, {**args, listed: kept}).model_dump(
                mode="json"
            )
            return normalised, await self.tiles.resolve(template, normalised, token, today)
        except (TileError, AppError):
            return None

    def _check_title(self, tile: _Tile) -> list[str]:
        """Replace a title that is too long, or names a figure or a month its payload lacks."""
        missing = self.figure_checks.missing_figures(
            answer=tile.title, sources=[tile.payload.model_dump_json()]
        )
        if len(tile.title) <= TITLE_MAX and not missing and _month_fits(tile=tile):
            return []
        before = tile.title
        tile.title = self.tiles.default_title(tile.payload)
        return [before]

    async def _signal_tile(self, signal: Signal, token: str, today: date) -> _Tile | None:
        if signal.template is None or signal.args is None:
            return None
        try:
            normalised = self.tiles.validate_args(signal.template, signal.args).model_dump(
                mode="json"
            )
            payload = await self.tiles.resolve(signal.template, normalised, token, today)
        except (TileError, AppError):
            return None
        return _Tile(
            template=signal.template,
            args=normalised,
            title=self.tiles.default_title(payload),
            payload=payload,
        )

    async def _ensure_hero(
        self, tiles: list[_Tile], signals: list[Signal], used: set[str], token: str, today: date
    ) -> str | None:
        """None when the model's first tile is a headline; otherwise what was done instead."""
        if tiles and tiles[0].template in HERO_TEMPLATES:
            return None
        before = tiles[0].template if tiles else "nothing"
        heroes = [s for s in signals if s.template in HERO_TEMPLATES][:HERO_TOP]
        # The strongest headline already on the board, else the strongest one, else any.
        for signal in heroes:
            key = tile_key(signal.template, signal.args or {})
            for index, tile in enumerate(tiles):
                if tile.key == key:
                    tiles.insert(0, tiles.pop(index))
                    return f"{before} is no headline; moved {signal.id} first"
        for signal in heroes:
            tile = await self._signal_tile(signal=signal, token=token, today=today)
            if tile is None or tile.key in used:
                continue
            used.add(tile.key)
            tiles.insert(0, tile)
            return f"{before} is no headline; put {signal.id} first"
        for index, tile in enumerate(tiles):
            if tile.template in HERO_TEMPLATES:
                tiles.insert(0, tiles.pop(index))
                return f"{before} is no headline; moved {tile.template} first"
        return f"{before} is no headline and no signal could replace it"

    async def _repair(
        self,
        tiles: list[_Tile],
        fewest: int,
        most: int,
        signals: list[Signal],
        used: set[str],
        token: str,
        today: date,
    ) -> int:
        added = 0
        for signal in signals:
            if len(tiles) >= fewest:
                break
            tile = await self._signal_tile(signal=signal, token=token, today=today)
            if tile is None or tile.key in used or _repeats(tile=tile, others=tiles):
                continue
            used.add(tile.key)
            tiles.append(tile)
            added += 1
        del tiles[most:]
        return added

    def _signal_used(self, signal: Signal, used: set[str]) -> bool:
        if signal.template is None or signal.args is None:
            return False
        return tile_key(signal.template, signal.args) in used


def _payment_rows(payload: AnyPayload) -> set[tuple[date, Any]]:
    if isinstance(payload, RegularPaymentsPayload):
        return {(row.next_due, row.amount_chf) for row in payload.rows}
    if isinstance(payload, DueSoonPayload | BillsUntilPaydayPayload):
        return {(row.due, row.amount_chf) for row in payload.rows}
    if isinstance(payload, BillPayload):
        return {(payload.due, payload.figure_chf)}
    return set()


def _repeats(tile: _Tile, others: list[_Tile]) -> bool:
    """Whether most payments of `tile` are shown by one of `others` already."""
    rows = _payment_rows(payload=tile.payload)
    if not rows:
        return False
    for other in others:
        if frozenset({tile.template, other.template}) in SINGLE_BILL_BESIDE_LIST:
            continue
        shared = rows & _payment_rows(payload=other.payload)
        if len(shared) >= len(rows) * OVERLAP_SHARE:
            return True
    return False


def _repeating(tiles: list[_Tile]) -> list[_Tile]:
    """The tiles whose payments an earlier tile on the board already shows; the first stays."""
    kept: list[_Tile] = []
    repeating = []
    for index, tile in enumerate(tiles):
        if index > 0 and _repeats(tile=tile, others=kept):
            repeating.append(tile)
        else:
            kept.append(tile)
    return repeating


def _month_fits(tile: _Tile) -> bool:
    """Whether a month the title names is the one month the tile's figures are about."""
    named = {
        number
        for name, number in MONTH_NUMBERS.items()
        if re.search(rf"\b{name}\b", tile.title, re.IGNORECASE)
    }
    if not named:
        return True
    payload = tile.payload
    if isinstance(payload, MerchantSpendingPayload):
        same = payload.date_from.month == payload.date_to.month
        return same and named == {payload.date_from.month}
    if isinstance(payload, CardBillPayload):
        return named == {int(payload.period[5:7])}
    return False
