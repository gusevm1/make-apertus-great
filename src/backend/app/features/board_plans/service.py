import asyncio
import calendar
import re
from datetime import date
from typing import Any

from app.clients.apertus import ApertusClient, LLMResult, Model
from app.core.errors import AppError
from app.core.provenance import Check
from app.features.board_plans import digest
from app.features.board_plans.digest import HERO_TEMPLATES, HERO_TOP, Raw, tile_key
from app.features.board_plans.prompts import board_prompt, profile_prompt
from app.features.board_plans.schemas import (
    OWN_TILE,
    BoardChoice,
    CustomerDigest,
    DroppedTile,
    Idea,
    IdeaChoice,
    PlanAnswer,
    PlannedBoard,
    PlannedBoards,
    PlannedTile,
    Signal,
    TileChoice,
    board_schema,
    profile_schema,
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

# Two calls in a row stay under Vercel's 120 s for a forwarded request.
CALL_TIMEOUT_SECONDS = 55
MAIN_MIN, MAIN_MAX = 5, 7
SIDE_MIN, SIDE_MAX = 3, 5
REQUEST_MIN, REQUEST_MAX = 2, 5
# A requested board is filled with related signals only up to this many tiles.
REQUEST_FILLED = 2
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
EXPECTED_LABEL_MAX = 40
# A tile title is a few plain words; longer, or with a filler word, it gets the default title.
TITLE_SHORT = 28
FILLER = re.compile(
    r"\b(upcoming|expected|overview|progress|late|total|current|trend|breakdown)\b", re.IGNORECASE
)
# A date the model wrote, such as "30.11.2026" or "30 Nov"; the prompt forbids them.
DATE = re.compile(
    r"\b\d{1,2}\.\s?\d{1,2}\.|\b\d{1,2}\.?\s(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
    re.IGNORECASE,
)
# A board name is a tab label.
NAME_WORDS, NAME_CHARS = 3, 24
PAYDAY_TEMPLATES = {"payday_balance", "bills_until_payday"}
# The default name of a first board by its hero's template.
HERO_NAMES = {
    "payday_balance": "Until payday",
    "bills_until_payday": "Until payday",
    "mortgage": "The house",
    "income_and_spending": "Every month",
}
# Two tiles of these templates show the same months.
SAME_MONTHS = frozenset({"monthly_spending", "income_and_spending"})
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
        customer, _ = await self._read_customer(token=token, today=today)
        return customer

    async def _read_customer(
        self, token: str, today: date
    ) -> tuple[CustomerDigest, dict[str, AnyPayload]]:
        """The digest, and the resolved tile of every signal that has one, by signal id."""
        raw = await self._read_raw(token=token, today=today)
        resolved = await self._resolve_all(
            tiles=digest.candidates(raw=raw), token=token, today=today
        )
        signals = digest.signals(raw=raw, resolved=resolved)
        payloads = {}
        for signal in signals:
            if signal.template is not None and signal.args is not None:
                payloads[signal.id] = resolved[tile_key(signal.template, signal.args)]
                # The same shape as a validated tile, so the two compare.
                signal.args = self.tiles.validate_args(signal.template, signal.args).model_dump(
                    mode="json"
                )
        customer = CustomerDigest(
            text=digest.facts_text(raw=raw), signals=signals, names=digest.names(raw=raw)
        )
        return customer, payloads

    @staticmethod
    def _distinct(customer: CustomerDigest, payloads: dict[str, AnyPayload]) -> list[Signal]:
        """The signals whose tile shows something no stronger signal's tile shows already."""
        kept: list[_Tile] = []
        distinct = []
        for signal in customer.signals:
            # Its tile lists the payments but not the old prices, so it cannot show the rise.
            if signal.template is None or signal.args is None or signal.kind == "price_rise":
                continue
            tile = _Tile(
                template=signal.template, args=signal.args, title="", payload=payloads[signal.id]
            )
            if _repeats(tile=tile, others=kept):
                continue
            kept.append(tile)
            distinct.append(signal)
        return distinct

    async def _ask(
        self,
        customer: CustomerDigest,
        offered: list[Signal],
        request: str | None,
        existing: list[str] | None,
    ) -> tuple[PlanAnswer, LLMResult[Any]]:
        """The plan from two small calls: who the customer is, then the tiles."""
        labels = {digest.label(signal=s): s for s in offered}
        heroes = [digest.label(signal=s) for s in digest.hero_candidates(signals=offered)]
        # A signal whose tile repeats a stronger one's is a fact only.
        signals_text = digest.signals_text(
            signals=[
                s if s in offered else s.model_copy(update={"template": None})
                for s in customer.signals
            ]
        )
        profile_call = self.apertus.structured(
            profile_prompt(
                facts=customer.text,
                signals=signals_text,
                heroes=[f"{h}: {labels[h].text}" for h in heroes or list(labels)],
            ),
            schema=profile_schema(
                labels=list(labels),
                heroes=heroes or list(labels),
                late_income=any(
                    labels[h].template == "payday_balance"
                    and (labels[h].args or {}).get("expected_from") is not None
                    for h in heroes
                ),
            ),
            model=Model.SMART,
            purpose="board_profile",
            timeout_seconds=CALL_TIMEOUT_SECONDS,
            json_schema_mode=True,
        )

        def tiles_call(kind: str, question: str, hero: str | None):
            rest = [label for label in labels if label != hero]
            return self.apertus.structured(
                board_prompt(
                    facts=customer.text,
                    signals=signals_text,
                    kind=kind,
                    question=question,
                    hero="" if hero is None else f"{hero}: {labels[hero].text}",
                    request=request,
                    existing=existing,
                ),
                schema=board_schema(
                    labels=rest,
                    names=customer.names,
                    first=rest if request is not None else None,
                    second=request is None,
                ),
                model=Model.SMART,
                purpose="board_tiles",
                timeout_seconds=CALL_TIMEOUT_SECONDS,
                json_schema_mode=True,
            )

        if request is None:
            profile = await profile_call
            hero = profile.content.hero
            tiles = await tiles_call(
                kind=profile.content.kind, question=profile.content.question, hero=hero
            )
            latency = profile.latency_ms + tiles.latency_ms
            question = profile.content.question
        else:
            profile, tiles = await asyncio.gather(
                profile_call, tiles_call(kind="", question=request, hero=None)
            )
            hero = None
            latency = max(profile.latency_ms, tiles.latency_ms)
            question = request
        board = tiles.content
        uses = board.signals.model_dump(by_alias=True)
        rest = [label for label in labels if label != hero]
        main_places = {"main"}

        def placed(places: set[str]) -> list[TileChoice]:
            # The server's order, strongest first; the model chose and titled.
            return [
                TileChoice(signal=labels[label].id, title=uses[label]["title"])
                for label in rest
                if uses[label]["use"] in places
            ]

        def own(place: str) -> list[TileChoice]:
            return [
                _choice(pick=pick)
                for pick in board.own
                if getattr(pick, "board", "main") == place
            ]

        if hero is not None:
            main = placed(places=main_places) + own(place="main")
            main = [_hero_choice(signal=labels[hero], profile=profile.content), *main]
        else:
            # What answers the request, then the model's own tiles; a related signal only fills
            # a board that would be thin, as it drifts off the request.
            main = placed(places={"answers"}) + own(place="main")
            first = board.first
            wanted = (
                own(place="main")[:1]
                if first == OWN_TILE
                else [c for c in main if first in labels and c.signal == labels[first].id]
            )
            if not wanted and first in labels:
                wanted = [TileChoice(signal=labels[first].id, title=uses[first]["title"])]
            main = wanted + [c for c in main if c not in wanted]
            for choice in placed(places={"related"}):
                if len(main) >= REQUEST_FILLED:
                    break
                main.append(choice)
        boards = [BoardChoice(name=board.name, tiles=main)]
        second = placed(places={"second"}) + own(place="second")
        if request is None and second:
            boards.append(BoardChoice(name=board.second_name or "", tiles=second))
        ideas = [
            IdeaChoice(title=uses[label]["title"], signal=labels[label].id)
            for label in rest
            if uses[label]["use"] == "idea"
        ]
        answer = PlanAnswer(
            kind=profile.content.kind,
            evidence=[f"{labels[e].id}: {labels[e].text}" for e in profile.content.evidence],
            question=question,
            boards=boards,
            ideas=ideas,
        )
        return answer, LLMResult(
            content=answer,
            model=tiles.model,
            latency_ms=latency,
            tokens_in=None,
            tokens_out=None,
        )

    async def plan_boards(
        self,
        token: str,
        today: date,
        request: str | None = None,
        existing: list[str] | None = None,
    ) -> PlannedBoards:
        """The customer's first boards, or one board for `request`, validated and ready to store."""
        customer, payloads = await self._read_customer(token=token, today=today)
        answer, result = await self._ask(
            customer=customer,
            offered=self._distinct(customer=customer, payloads=payloads),
            request=request,
            existing=existing,
        )
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
            boards.append(("Overview" if request is None else "New board", []))

        hero_detail = None
        if request is None:
            hero_detail = await self._ensure_hero(
                tiles=boards[0][1], signals=customer.signals, used=used, token=token, today=today
            )
        # A thin second board is left out rather than filled with tiles off its theme; its
        # tiles are free again for the main board.
        for name, board_tiles in boards[1:]:
            if len(board_tiles) < SIDE_MIN:
                used -= {tile.key for tile in board_tiles}
        boards = [board for index, board in enumerate(boards) if index == 0 or len(board[1]) >= SIDE_MIN]
        repaired = []
        # A requested board is never filled with the strongest signals, which are off its topic.
        mended = boards[:1] if request is None else []
        for (name, board_tiles), (fewest, most) in zip(mended, limits, strict=False):
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

        boards = [
            (_board_name(name=name, index=index, tiles=board_tiles, request=request), board_tiles)
            for index, (name, board_tiles) in enumerate(boards)
        ]
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
        """Replace a title that is too long, or names a figure, date or month its payload lacks."""
        before = tile.title
        # A filler word is left out ("Emergency fund progress" is "Emergency fund").
        tile.title = re.sub(r"\s{2,}", " ", FILLER.sub("", tile.title)).strip(" ,:-")
        missing = self.figure_checks.missing_figures(
            answer=tile.title, sources=[tile.payload.model_dump_json()]
        )
        dated = DATE.search(tile.title) is not None
        # "Until payday" wording belongs to the tiles about payday.
        payday = "payday" in tile.title.casefold() and tile.template not in PAYDAY_TEMPLATES
        short = 0 < len(tile.title) <= TITLE_SHORT and not payday
        if short and not missing and not dated and _month_fits(tile=tile):
            return []
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
    if any(frozenset({tile.template, other.template}) == SAME_MONTHS for other in others):
        return True
    if any(_same_account(first=tile, second=other) for other in others):
        return True
    rows = _payment_rows(payload=tile.payload)
    if not rows:
        return False
    for other in others:
        if frozenset({tile.template, other.template}) in SINGLE_BILL_BESIDE_LIST:
            continue
        theirs = _payment_rows(payload=other.payload)
        if not theirs:
            continue
        # Either list mostly inside the other: the smaller one shows nothing new.
        if len(rows & theirs) >= min(len(rows), len(theirs)) * OVERLAP_SHARE:
            return True
    return False


def _same_account(first: _Tile, second: _Tile) -> bool:
    """An account_balances tile of only the account a savings_goal tile already shows."""
    pair = {first.template: first, second.template: second}
    if set(pair) != {"account_balances", "savings_goal"}:
        return False
    shown = set(pair["account_balances"].args["account_ids"])
    return shown <= {pair["savings_goal"].args["account_id"]}


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


def _hero_choice(signal: Signal, profile: Any) -> TileChoice:
    """The hero's tile; a late income on payday_balance gets the customer's own words for it."""
    label = (getattr(profile, "expected_label", None) or "").strip()
    args = signal.args or {}
    if (
        signal.template != "payday_balance"
        or args.get("expected_from") is None
        or not label
        or re.search(r"\d", label)
        # Their own words, not the payer's name, which the tile shows already.
        or any(part.casefold() in label.casefold() for part in args["expected_from"].split())
        or len(label) > EXPECTED_LABEL_MAX
    ):
        return TileChoice(signal=signal.id, title=profile.hero_title)
    return TileChoice(
        template=signal.template,
        args={**args, "expected_label": label},
        title=profile.hero_title,
    )


def _choice(pick: Any) -> TileChoice:
    """An own tile of the model, as a template with arguments."""
    args = {
        "merchant_spending": {"merchants": pick.names, "period": pick.period or "this_month"},
        "regular_payments": {"payees": pick.names},
        "account_balances": {"account_ids": pick.names},
        "bill": {"payment_id": pick.names[0]},
    }[pick.template]
    return TileChoice(template=pick.template, args=args, title=pick.title)


def name_fits(name: str) -> bool:
    """Whether a board name reads as a tab label: one to three words, no question."""
    return 0 < len(name) <= NAME_CHARS and len(name.split()) <= NAME_WORDS and "?" not in name


def _board_name(name: str, index: int, tiles: list[_Tile], request: str | None) -> str:
    """The model's name when it fits a tab, else a default from the hero or the first tile."""
    name = name.strip().rstrip(".")
    hero = tiles[0].template if tiles else None
    # "Until payday" belongs to a payday hero only.
    off_payday = "payday" in name.casefold() and hero not in PAYDAY_TEMPLATES
    if name_fits(name=name) and not (index == 0 and request is None and off_payday):
        return name
    if request is None and index == 0:
        return HERO_NAMES.get(hero or "", "Overview")
    first = tiles[0].title if tiles else ""
    return first if name_fits(name=first) else "New board"
