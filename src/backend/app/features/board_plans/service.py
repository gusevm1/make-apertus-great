import asyncio
import calendar
import dataclasses
import re
import time
from collections.abc import Callable
from datetime import date
from typing import Any, Literal

from app.clients.apertus import ApertusClient, LLMResult, Model
from app.core.errors import AppError, UpstreamError
from app.core.provenance import Check
from app.features.board_plans import digest
from app.features.board_plans.digest import HERO_TEMPLATES, HERO_TOP, Raw, tile_key
from app.features.board_plans.prompts import (
    board_prompt,
    entry_prompt,
    profile_prompt,
    request_prompt,
)
from app.features.board_plans.schemas import (
    BoardChoice,
    CustomerDigest,
    DroppedTile,
    EntryCheck,
    Idea,
    IdeaChoice,
    PlanAnswer,
    PlannedBoard,
    PlannedBoards,
    PlannedTile,
    RequestKeywords,
    Signal,
    TileChoice,
    TraceItem,
    TraceStep,
    board_schema,
    profile_schema,
    request_schema,
)
from app.features.figure_checks.service import FigureCheckService
from app.features.ledger.service import LedgerService
from app.features.recurring_payments.service import RecurringPaymentService
from app.features.tiles.schemas import (
    AccountBalancesPayload,
    AnyPayload,
    BillPayload,
    BillsUntilPaydayPayload,
    CardBillPayload,
    DueSoonPayload,
    ExpectedIncomePayload,
    MerchantSpendingPayload,
    NetWorthPayload,
    Pillar3aPayload,
    RegularPaymentsPayload,
    SavingsGoalPayload,
    SecuritiesPayload,
)
from app.features.tiles.service import TileError, TileService

# Each planning call has its own budget, the client's retries included; two in a row stay
# under a minute, and the server's ranking takes over when one runs out.
CALL_TIMEOUT_SECONDS = 20
CALL_BUDGET_SECONDS = 28
# The check of one picked payee on its own, several at once.
ENTRY_CHECK_SECONDS = 12
ENTRY_CHECKS_PARALLEL = 4
PLAN_FAILURES = (TimeoutError, UpstreamError)
RANKED_KIND = "Not classified: the model did not answer in time."
NO_ANSWER = "No answer in time. The server carries on with its own ranking of the findings."
NOT_PLANNED = (
    "The model did not answer in time; this board follows the server's ranking of your signals."
)
NOT_PICKED = (
    "The model did not answer in time; this board holds what your request names word for word."
)
NOTHING_FOUND = "Nothing in your accounts is about this request yet."
LOAN_UNKNOWN = (
    "The bank does not know how much of the loan is left; tell me the amount and I add it."
)
KEYWORD_MIN = 4
SUBSCRIPTION_REQUEST = re.compile(r"subscri|\babo\b|abonnement", re.IGNORECASE)
REQUEST_BILLS = 2
# An idea's board: its finding and what the request call found beside it.
REQUEST_IDEA_TILES = 3
IDEA_ALONE = "This board starts with the finding behind the idea; ask the chat to add more."
# The German words of a finding's kind, as the findings are written in English.
KIND_WORDS = {
    "mortgage_maturity": "Hypothek Haus house",
    "mortgage": "Hypothek Haus house",
    "private_loan": "Darlehen loan Rückzahlung",
    "instalments": "Raten Leasing instalment",
    "tax_bill": "Steuer Steuern tax",
    "reminder": "Mahnung Rechnung reminder bill",
    "large_bill": "Rechnung bill",
    "card_bill": "Kreditkarte card",
    "pillar_3a": "Säule Vorsorge pension",
}
STOP_WORDS = {
    "what",
    "does",
    "when",
    "have",
    "should",
    "about",
    "that",
    "this",
    "with",
    "keep",
    "want",
    "every",
    "month",
    "cost",
    "costs",
    "which",
    "decide",
    "there",
    "them",
    "they",
    "your",
    "from",
}
# For the keyword match without the model: the German word an English request means.
ENGLISH_WORDS = {
    "emergency": "Notgroschen",
    "subscription": "Abo",
    "house": "Haus",
    "mortgage": "Hypothek",
    "loan": "Darlehen",
    "parent": "Darlehen",
    "repa": "Rückzahlung",
    "trip": "Reise",
    "bill": "Rechnung",
    "reminder": "Mahnung",
    "tax": "Steuer",
}
# An idea's title when the model wrote none, by the kind of its signal.
IDEA_TITLES = {
    "instalments": "Instalments",
    "private_loan": "Paying back a loan",
    "fixed_costs": "Fixed costs",
    "price_rise": "What got dearer",
    "card_bill": "Credit card",
    "securities": "Securities",
    "pillar_3a": "Pillar 3a",
    "savings_pots": "Savings pots",
    "tax_bill": "Taxes",
    "reminder": "Open reminders",
    "spending": "Where the money goes",
    "cashflow": "In and out",
    "cashflow_negative": "In and out",
    "due_soon": "Bills due soon",
    "bills_before_payday": "Bills until payday",
}
# After a mortgage hero: the house and the decision first, the car and pillar 3a last.
MORTGAGE_ORDER = {
    "goal_progress": 0,
    "goal_far": 0,
    "goal_reached": 0,
    "savings_pots": 1,
    "due_soon": 2,
    "fixed_costs": 2,
    "cashflow": 3,
    "pillar_3a": 5,
    "instalments": 5,
}
MORTGAGE_REST = 4
# Ideas about one concrete thing in the customer's life, the most concrete first.
CONCRETE_KINDS = [
    "instalments",
    "private_loan",
    "goal_far",
    "goal_progress",
    "goal_reached",
    "reminder",
    "tax_bill",
    "large_bill",
    "card_bill",
    "income_regular",
    "income_late",
    "pillar_3a",
    "securities",
    "fixed_costs",
    "savings_pots",
]
# Findings about the whole month make no board of their own.
NO_IDEA_KINDS = {
    "spending",
    "cashflow",
    "due_soon",
    "bills_before_payday",
    "payday",
    "payday_tight",
}
# Findings about the whole month, which a requested board about one thing never needs.
GENERAL_KINDS = {
    "spending",
    "cashflow",
    "cashflow_negative",
    "due_soon",
    "bills_before_payday",
    "payday",
    "payday_tight",
    "fixed_costs",
    "savings_pots",
    "depot_large",
    "income_regular",
}
MAIN_MIN, MAIN_MAX = 5, 7
SIDE_MIN, SIDE_MAX = 3, 5
REQUEST_MIN, REQUEST_MAX = 2, 5
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
    def __init__(
        self, template: str, args: dict[str, Any], title: str, payload: AnyPayload
    ) -> None:
        self.template = template
        self.args = args
        self.title = title
        self.payload = payload

    @property
    def key(self) -> str:
        return tile_key(self.template, self.args)


USE_WORDS = {
    "main": "For the board",
    "second": "For a second board",
    "idea": "As an idea for later",
    "no": "Left out",
}


class _Trace:
    """The steps of one plan in order, each reported to `on_step` at its start and its end."""

    def __init__(self, on_step: Callable[[TraceStep], None] | None) -> None:
        self.steps: list[TraceStep] = []
        self.on_step = on_step
        self.started = 0.0

    def start(self, name: str, title: str, actor: Literal["server", "apertus"], reads: str) -> None:
        self.started = time.monotonic()
        self.steps.append(TraceStep(name=name, title=title, actor=actor, reads=reads))
        self._report()

    def end(
        self, summary: str, items: list[TraceItem] | None = None, has_failed: bool = False
    ) -> None:
        step = self.steps[-1]
        step.is_done = True
        step.has_failed = has_failed
        step.seconds = round(time.monotonic() - self.started, 1)
        step.summary = summary
        step.items = items or []
        self._report()

    def _report(self) -> None:
        if self.on_step is not None:
            self.on_step(self.steps[-1].model_copy())


def _count(number: int, word: str) -> str:
    return f"{number} {word}" if number == 1 else f"{number} {word}s"


def _kind_words(signal: Signal) -> str:
    return signal.kind.replace("_", " ")


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
        customer, _, _ = await self._read_customer(
            token=token, today=today, trace=_Trace(on_step=None)
        )
        return customer

    async def _read_customer(
        self, token: str, today: date, trace: _Trace
    ) -> tuple[CustomerDigest, dict[str, AnyPayload], Raw]:
        """The digest, the resolved tile of every signal that has one by signal id, the raw read."""
        trace.start(
            name="read_bank",
            title="Read the customer from the bank",
            actor="server",
            reads="The banking API, with the customer's own token",
        )
        raw = await self._read_raw(token=token, today=today)
        counts = {
            "Accounts": len(raw.accounts),
            "Bookings": len(raw.rows),
            "Upcoming payments": len(raw.upcoming),
            "Regular payments": len(raw.recurring.recurring),
            "Instalment plans": len(raw.recurring.instalment_plans),
            "Loans": len(raw.loans),
            "Cards": len(raw.cards),
            "Depot": 1 if raw.portfolio.get("total_value_chf") else 0,
        }
        trace.end(
            summary=f"{len(raw.accounts)} accounts, {len(raw.rows)} bookings, "
            f"{len(raw.upcoming)} upcoming payments",
            items=[TraceItem(label=name, text=str(count)) for name, count in counts.items()],
        )
        candidates = digest.candidates(raw=raw)
        trace.start(
            name="signals",
            title="Compute the findings",
            actor="server",
            reads=f"{_count(len(candidates), 'possible tile')}, each computed from the bank's data",
        )
        resolved = await self._resolve_all(tiles=candidates, token=token, today=today)
        signals = digest.signals(raw=raw, resolved=resolved)
        trace.end(
            summary=f"{_count(len(signals), 'finding')}, the most pressing first",
            items=[
                TraceItem(label=f"{signal.id} {_kind_words(signal=signal)}", text=signal.text)
                for signal in signals
            ],
        )
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
        return customer, payloads, raw

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

    async def _ask_first(
        self,
        customer: CustomerDigest,
        offered: list[Signal],
        incomes: dict[str, str],
        trace: _Trace,
    ) -> tuple[PlanAnswer, str | None, int]:
        """The first boards from two small calls; the server's ranking when the model fails."""
        labels = {digest.label(signal=s): s for s in offered}
        heroes = [digest.label(signal=s) for s in digest.hero_candidates(signals=offered)]
        heroes = heroes or list(labels)
        # A signal whose tile repeats a stronger one's is a fact only.
        signals_text = digest.signals_text(
            signals=[
                s if s in offered else s.model_copy(update={"template": None})
                for s in customer.signals
            ]
        )
        late = {
            h: incomes.get((labels[h].args or {}).get("expected_from") or "", "")
            for h in heroes
            if labels[h].template == "payday_balance"
            and (labels[h].args or {}).get("expected_from") is not None
        }
        trace.start(
            name="board_profile",
            title="Who is this customer?",
            actor="apertus",
            reads=f"The customer's facts, {_count(len(customer.signals), 'finding')} and "
            f"{_count(len(heroes), 'candidate')} for the first tile",
        )
        try:
            profile = await self._structured(
                messages=profile_prompt(
                    facts=customer.text,
                    signals=signals_text,
                    heroes=[f"{h}: {labels[h].text}" for h in heroes],
                    booked="; ".join(f'"{text}"' for text in late.values()),
                ),
                schema=profile_schema(labels=list(labels), heroes=heroes, late_income=bool(late)),
                purpose="board_profile",
            )
        except PLAN_FAILURES:
            trace.end(summary=NO_ANSWER, has_failed=True)
            return _ranked_answer(labels=labels, hero=heroes[0] if heroes else None), None, 0
        hero = profile.content.hero
        hero_tile = _hero_choice(
            signal=labels[hero], profile=profile.content, booked=late.get(hero)
        )
        trace.end(
            summary=profile.content.kind,
            items=[
                TraceItem(label="Kind of customer", text=profile.content.kind),
                *(
                    TraceItem(label="Evidence", text=_evidence(signal=labels[e]))
                    for e in profile.content.evidence
                ),
                TraceItem(label="Their question", text=profile.content.question),
                *(
                    TraceItem(
                        label="For the first tile" if h == hero else "Not chosen",
                        text=f"{profile.content.hero_title}: {labels[h].text}"
                        if h == hero
                        else labels[h].text,
                        mark=None if h == hero else "dropped",
                    )
                    for h in heroes
                ),
            ],
        )
        trace.start(
            name="board_tiles",
            title="Which tiles, and what to call them?",
            actor="apertus",
            reads="The kind, the question, the first tile and the other "
            + _count(len(labels) - 1, "finding"),
        )
        try:
            tiles = await self._structured(
                messages=board_prompt(
                    facts=customer.text,
                    signals=signals_text,
                    kind=profile.content.kind,
                    question=profile.content.question,
                    hero=f"{hero}: {labels[hero].text}",
                ),
                schema=board_schema(
                    labels=[label for label in labels if label != hero],
                    names=customer.names,
                    first=None,
                    second=True,
                ),
                purpose="board_tiles",
            )
        except PLAN_FAILURES:
            trace.end(summary=NO_ANSWER, has_failed=True)
            ranked = _ranked_answer(labels=labels, hero=hero)
            ranked.boards[0].tiles[0] = hero_tile
            answer = ranked.model_copy(
                update={
                    "kind": profile.content.kind,
                    "evidence": [_evidence(signal=labels[e]) for e in profile.content.evidence],
                    "question": profile.content.question,
                }
            )
            return answer, None, profile.latency_ms
        board = tiles.content
        uses = board.signals.model_dump(by_alias=True)
        rest = [label for label in labels if label != hero]
        on_boards = [label for label in rest if uses[label]["use"] in {"main", "second"}]
        trace.end(
            summary=f"{_count(len(on_boards) + len(board.own), 'tile')} chosen beside the first, "
            f"{_count(len(rest) - len(on_boards), 'finding')} not on a board",
            items=[
                *(
                    TraceItem(
                        label=USE_WORDS[uses[label]["use"]],
                        text=f"{uses[label]['title']} ({_kind_words(signal=labels[label])})",
                        # A tick is the server's: only a checked tile gets one.
                        mark="dropped" if uses[label]["use"] == "no" else None,
                    )
                    for label in rest
                ),
                *(
                    TraceItem(
                        label="A tile of its own",
                        text=f"{pick.title}: {pick.template.replace('_', ' ')} of "
                        + ", ".join(pick.names),
                    )
                    for pick in board.own
                ),
            ],
        )

        def placed(place: str) -> list[TileChoice]:
            # The server's order, strongest first; the model chose and titled.
            return [
                TileChoice(signal=labels[label].id, title=uses[label]["title"])
                for label in rest
                if uses[label]["use"] == place
            ]

        def own(place: str) -> list[TileChoice]:
            return [_choice(pick=pick) for pick in board.own if pick.board == place]

        main = [*placed("main"), *own("main")]
        if labels[hero].template == "mortgage":
            # The blueprint of a house with a decision ahead: the house first, then the rest.
            by_id = {signal.id: signal for signal in labels.values()}
            main.sort(
                key=lambda c: MORTGAGE_ORDER.get(
                    by_id[c.signal].kind if c.signal in by_id else "", MORTGAGE_REST
                )
            )
        boards = [BoardChoice(name=board.name, tiles=[hero_tile, *main])]
        second = placed("second") + own("second")
        if second:
            boards.append(BoardChoice(name=board.second_name or "", tiles=second))
        answer = PlanAnswer(
            kind=profile.content.kind,
            evidence=[_evidence(signal=labels[e]) for e in profile.content.evidence],
            question=profile.content.question,
            boards=boards,
            # Every signal's title; the server picks the ideas from those left off the boards.
            ideas=[
                IdeaChoice(title=uses[label]["title"], signal=labels[label].id) for label in rest
            ],
        )
        return answer, tiles.model, profile.latency_ms + tiles.latency_ms

    async def _ask_request(
        self,
        request: str,
        customer: CustomerDigest,
        offered: list[Signal],
        lists: digest.RequestLists,
        existing: list[str] | None,
        payloads: dict[str, AnyPayload],
        trace: _Trace,
    ) -> tuple[PlanAnswer, str | None, int]:
        bills = next((s for s in offered if s.kind in {"bills_before_payday", "due_soon"}), None)
        """One requested board: the model picks the customer's things, the server builds tiles."""
        findings = {digest.label(signal=s): s for s in offered if s.kind not in GENERAL_KINDS}
        # An idea from the first plan carries its finding's sentence: that finding answers it.
        idea = next(
            (
                s
                for s in customer.signals
                if s.template is not None
                and (s.text in request or idea_text(signal=s, payload=payloads[s.id]) in request)
            ),
            None,
        )
        trace.start(
            name="board_request",
            title="What is this request about?",
            actor="apertus",
            reads=f"The request, {len(lists.payees) + len(lists.shops)} payees and shops, "
            f"{len(lists.payments)} open payments and {len(findings)} findings",
        )
        try:
            result = await self._structured(
                messages=request_prompt(
                    request=request,
                    lists=digest.request_text(lists=lists),
                    signals=digest.signals_text(signals=list(findings.values())),
                    existing=existing,
                ),
                schema=request_schema(entries=list(dict.fromkeys([*lists.payees, *lists.shops]))),
                purpose="board_request",
            )
        except PLAN_FAILURES:
            trace.end(
                summary="No answer in time. The server looks for the request's own words.",
                has_failed=True,
            )
            words = [
                w
                for w in re.findall(r"\w+", request)
                if len(w) >= KEYWORD_MIN and w.casefold() not in STOP_WORDS
            ]
            words += [
                german for english, german in ENGLISH_WORDS.items() if english in request.casefold()
            ]
            asked = RequestKeywords(keywords=words, costs_only=False, open_bills=False, name="")
            if idea is not None:
                asked = RequestKeywords(keywords=[], costs_only=False, open_bills=False, name="")
            answer = _request_answer(
                request=request, asked=asked, findings=findings, lists=lists, bills=bills
            )
            return _with_idea(answer=answer, idea=idea, request=request), None, 0
        asked = result.content
        keywords = [k for k in [*asked.entries, *asked.keywords] if k.strip()]
        matched = [p for p, text in lists.payments.items() if _matches(keywords, text)]
        trace.end(
            summary=f"{asked.name}: {len(asked.entries)} payees picked, "
            f"{len(matched)} open payments matched",
            items=[
                TraceItem(label="Board name", text=asked.name),
                *(TraceItem(label="Picked", text=entry) for entry in asked.entries),
                *(TraceItem(label="Looks for", text=word) for word in asked.keywords),
            ],
        )
        picked = list(dict.fromkeys([*asked.entries, *matched]))
        trace.start(
            name="board_request_entries",
            title="Is each pick really about the request?",
            actor="apertus",
            reads=f"{len(picked)} picks, each checked on its own",
        )
        kept, kept_payments = await asyncio.gather(
            self._checked_entries(request=request, entries=asked.entries, lists=lists),
            self._checked_entries(request=request, entries=matched, lists=lists),
        )
        still = {*kept, *kept_payments}
        trace.end(
            summary=f"{len(still)} of {len(picked)} kept",
            items=[
                TraceItem(
                    label="Kept" if pick in still else "Not about it",
                    text=lists.payments.get(pick) or pick,
                    mark="kept" if pick in still else "dropped",
                )
                for pick in picked
            ],
        )
        asked = asked.model_copy(update={"entries": kept})
        # An open bill the keywords found is checked on its own like a payee.
        lists = dataclasses.replace(
            lists,
            payments={
                p: text
                for p, text in lists.payments.items()
                if p not in matched or p in kept_payments
            },
        )
        answer = _request_answer(
            request=request, asked=asked, findings=findings, lists=lists, bills=bills
        )
        return (
            _with_idea(answer=answer, idea=idea, request=request),
            result.model,
            result.latency_ms,
        )

    async def _checked_entries(
        self, request: str, entries: list[str], lists: digest.RequestLists
    ) -> list[str]:
        """The picked payees that a check of each on its own still finds about the request."""
        words = [
            w
            for w in re.findall(r"\w+", request)
            # A year is in many texts (a holiday in January 2027 is not the trip of 2027).
            if len(w) >= KEYWORD_MIN and w.casefold() not in STOP_WORDS and not w.isdigit()
        ]
        semaphore = asyncio.Semaphore(ENTRY_CHECKS_PARALLEL)

        async def check(name: str) -> bool:
            text = lists.payments.get(name) or (
                f"{name}: {lists.payees.get(name) or lists.shops.get(name) or ''}"
            )
            # The request's own words in the entry's texts: no check needed.
            if _matches(words, text):
                return True
            async with semaphore:
                try:
                    result = await self._structured(
                        messages=entry_prompt(request=request, entry=text),
                        schema=EntryCheck,
                        purpose="board_request_entry",
                        budget_seconds=ENTRY_CHECK_SECONDS,
                    )
                except PLAN_FAILURES:
                    return False
            return result.content.about == "yes"

        names = list(dict.fromkeys(entries))
        verdicts = await asyncio.gather(*(check(name) for name in names))
        return [name for name, keep in zip(names, verdicts, strict=True) if keep]

    async def _structured(
        self,
        messages: Any,
        schema: Any,
        purpose: str,
        budget_seconds: float = CALL_BUDGET_SECONDS,
    ) -> LLMResult[Any]:
        # One budget per call: the client's own retries happen inside it.
        return await asyncio.wait_for(
            self.apertus.structured(
                messages,
                schema=schema,
                model=Model.SMART,
                purpose=purpose,
                timeout_seconds=min(CALL_TIMEOUT_SECONDS, budget_seconds),
                json_schema_mode=True,
            ),
            timeout=budget_seconds,
        )

    async def plan_boards(
        self,
        token: str,
        today: date,
        request: str | None = None,
        existing: list[str] | None = None,
        on_step: Callable[[TraceStep], None] | None = None,
    ) -> PlannedBoards:
        """The customer's first boards, or one board for `request`, validated and ready to store."""
        trace = _Trace(on_step=on_step)
        customer, payloads, raw = await self._read_customer(token=token, today=today, trace=trace)
        offered = self._distinct(customer=customer, payloads=payloads)
        if request is None:
            answer, model, latency_ms = await self._ask_first(
                customer=customer,
                offered=offered,
                incomes=digest.income_texts(raw=raw),
                trace=trace,
            )
        else:
            answer, model, latency_ms = await self._ask_request(
                request=request,
                customer=customer,
                offered=offered,
                lists=digest.request_lists(raw=raw),
                existing=existing,
                payloads=payloads,
                trace=trace,
            )
        trace.start(
            name="check_tiles",
            title="Check every tile and compute its figures",
            actor="server",
            reads="Each chosen tile, validated and filled from the banking API",
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
                # On a requested board, a later tile titled like the board or the request says
                # nothing about what it shows.
                said = tile.title.casefold()
                if (
                    request is not None
                    and board_tiles
                    and (said == choice.name.strip().casefold() or said in request.casefold())
                ):
                    tile.title = self.tiles.default_title(tile.payload)
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
        for _, board_tiles in boards[1:]:
            if len(board_tiles) < SIDE_MIN:
                used -= {tile.key for tile in board_tiles}
        boards = [
            board for index, board in enumerate(boards) if index == 0 or len(board[1]) >= SIDE_MIN
        ]
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
        ideas = (
            []
            if request is not None
            else self._ideas(answer=answer, signals=customer.signals, used=used, payloads=payloads)
        )
        dropped += answer.notes
        if request is not None and not boards[0][1] and not dropped:
            dropped.append(DroppedTile(title=request[:TITLE_SHORT], reason=NOTHING_FOUND))
        checks.append(
            Check(
                name="planned_by_model",
                passed=model is not None,
                detail=None
                if model is not None
                else NOT_PLANNED
                if request is None
                else NOT_PICKED,
            )
        )
        placed = [(name, tile) for name, board_tiles in boards for tile in board_tiles]
        trace.end(
            summary=f"{_count(len(placed), 'tile')} on {_count(len(boards), 'board')}"
            + (f", {len(dropped)} dropped" if dropped else ""),
            items=[
                *(
                    TraceItem(
                        label=name,
                        text=f"{tile.title}: CHF {digest.chf(tile.payload.figure_chf)}, "
                        f"from {tile.payload.source.label}",
                        mark="kept",
                    )
                    for name, tile in placed
                ),
                *(
                    TraceItem(label="Dropped", text=f"{d.title}: {d.reason}", mark="dropped")
                    for d in dropped
                ),
                *(TraceItem(label="Idea for later", text=idea.title) for idea in ideas),
                *(
                    TraceItem(label="Check", text=f"{check.name}: {check.detail}")
                    for check in checks
                    if not check.passed and check.detail is not None
                ),
            ],
        )
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
            model=model or "server",
            latency_ms=latency_ms,
            checks=checks,
            trace=trace.steps,
        )

    def _ideas(
        self,
        answer: PlanAnswer,
        signals: list[Signal],
        used: set[str],
        payloads: dict[str, AnyPayload],
    ) -> list[Idea]:
        """Three further boards: the strongest signals off the boards that can carry one."""
        titles = {idea.signal: idea.title for idea in answer.ideas}
        free = [
            signal
            for signal in signals
            if signal.template is not None
            # A price rise's tile shows no old prices; its board would not show the rise.
            and signal.kind not in {"payday", "payday_tight", "price_rise"}
            and not self._signal_used(signal, used)
        ]
        # Findings about one concrete thing first, in this order; the whole month only to fill.
        rank = {kind: index for index, kind in enumerate(CONCRETE_KINDS)}
        ranked = sorted(free, key=lambda s: rank.get(s.kind, len(rank) + (s.kind in NO_IDEA_KINDS)))
        ideas: list[Idea] = []
        for signal in ranked:
            title = (titles.get(signal.id) or "").strip()
            title = re.sub(r"\s{2,}", " ", FILLER.sub("", title)).strip(" ,:-")
            if not 0 < len(title) <= TITLE_SHORT or DATE.search(title):
                title = IDEA_TITLES.get(signal.kind) or self.tiles.default_title(
                    payloads[signal.id]
                )
            if any(idea.title.casefold() == title.casefold() for idea in ideas):
                continue
            ideas.append(
                Idea(title=title, text=idea_text(signal=signal, payload=payloads[signal.id]))
            )
            if len(ideas) == IDEAS_MAX:
                break
        return ideas

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
            narrowed = await self._narrowed(template=template, args=args, token=token, today=today)
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
        # Fewer names than the title was written for: it would promise the missing ones.
        if (
            listed is not None
            and len(normalised[listed]) < len(args.get(listed) or [])
            and len(normalised[listed]) < NARROWED_KEPT_TITLE
        ):
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
        # A title starts with a capital, as a person writes a label.
        tile.title = tile.title[:1].upper() + tile.title[1:]
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
            key = tile_key(signal.template or "", signal.args or {})
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
    if any(_same_payee(first=tile, second=other) for other in others):
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


def _same_payee(first: _Tile, second: _Tile) -> bool:
    """A bill of a payee whose regular payments another tile lists already."""
    pair = {first.template: first, second.template: second}
    if set(pair) != {"bill", "regular_payments"}:
        return False
    bill = pair["bill"].payload
    listed = pair["regular_payments"].payload
    if not isinstance(bill, BillPayload) or not isinstance(listed, RegularPaymentsPayload):
        return False
    # The bank names one payee a little differently in a bill and in a standing order.
    billed = bill.payee.split()[0].casefold()
    return any(row.payee.split()[0].casefold() == billed for row in listed.rows)


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


def _hero_choice(signal: Signal, profile: Any, booked: str | None) -> TileChoice:
    """The hero's tile; a late income on payday_balance gets the customer's own words for it."""
    args = signal.args or {}
    if signal.template != "payday_balance" or args.get("expected_from") is None:
        return TileChoice(signal=signal.id, title=profile.hero_title)
    label = (getattr(profile, "expected_label", None) or "").strip()
    fits = (
        label
        and re.search(r"\d", label) is None
        and len(label) <= EXPECTED_LABEL_MAX
        # Their own words, not the payer's name, which the tile shows already.
        and not any(part.casefold() in label.casefold() for part in args["expected_from"].split())
    )
    if not fits:
        label = digest.income_label(text=booked or "") or ""
    if not label:
        return TileChoice(signal=signal.id, title=profile.hero_title)
    if not label.casefold().startswith("the "):
        label = f"the {label}"
    return TileChoice(
        template=signal.template, args={**args, "expected_label": label}, title=profile.hero_title
    )


def _evidence(signal: Signal) -> str:
    return f"{signal.id}: {signal.text}"


def _ranked_answer(labels: dict[str, Signal], hero: str | None) -> PlanAnswer:
    """The first board from the server's ranking alone: the hero, then the strongest signals."""
    order = [label for label in labels if label != hero]
    if hero is not None:
        order.insert(0, hero)
    return PlanAnswer(
        kind=RANKED_KIND,
        evidence=[_evidence(signal=labels[label]) for label in order[:3]],
        question="",
        boards=[
            BoardChoice(name="", tiles=[TileChoice(signal=labels[label].id) for label in order])
        ],
        ideas=[],
    )


def _matches(keywords: list[str], text: str) -> bool:
    """Whether a keyword stands in the text as a word or the start of one, case ignored."""
    words = re.findall(r"\w+", text.casefold())
    joined = " ".join(words)
    for keyword in keywords:
        parts = re.findall(r"\w+", keyword.casefold())
        # A year alone marks many texts (a holiday in January 2027 is not the trip of 2027).
        if not parts or len("".join(parts)) < KEYWORD_MIN - 1 or "".join(parts).isdigit():
            continue
        if re.search(r"\b" + r"\s+".join(map(re.escape, parts)), joined):
            return True
    return False


def _with_idea(answer: PlanAnswer, idea: Signal | None, request: str) -> PlanAnswer:
    """An idea's board is the finding it was made from; others drift off it, so none is added."""
    if idea is None:
        return answer
    title = request.split(".", 1)[0].strip()
    name = answer.boards[0].name or title
    return answer.model_copy(
        update={
            "boards": [BoardChoice(name=name, tiles=[TileChoice(signal=idea.id, title=title)])],
            # The selection's own notes (such as the loan's) belong to tiles left out here.
            "notes": [DroppedTile(title=title, reason=IDEA_ALONE)],
        }
    )


def _request_answer(
    request: str,
    asked: RequestKeywords,
    findings: dict[str, Signal],
    lists: digest.RequestLists,
    bills: Signal | None,
) -> PlanAnswer:
    """A requested board's tiles, built by type from what its keywords find, most direct first."""
    keywords = [k.strip() for k in [*asked.entries, *asked.keywords] if k.strip()]

    def account_text(account: dict[str, Any]) -> str:
        return f"{account['name']} {account.get('purpose')} {account.get('savings_goal') or ''}"

    found = [
        label
        for label, s in findings.items()
        if _matches(keywords, f"{s.text} {KIND_WORDS.get(s.kind, '')}")
    ]
    # Payees the model named win over keywords, which also catch payees off the topic.
    if asked.entries:
        payees = [n for n in lists.payees if n in asked.entries]
        shops = [n for n in lists.shops if n in asked.entries]
    else:
        payees = [n for n, text in lists.payees.items() if _matches(keywords, f"{n} {text}")]
        shops = [n for n, text in lists.shops.items() if _matches(keywords, f"{n} {text}")]
    if SUBSCRIPTION_REQUEST.search(request):
        # Subscriptions by the bank's own payment texts, not by the model's pick.
        payees, shops = list(lists.subscriptions), []
    # A transfer to the customer's own account is no cost of anything.
    own = {account["name"] for account in lists.accounts.values()}
    payees = [n for n in payees if not any(n.startswith(name) for name in own)]
    payments = [p for p, text in lists.payments.items() if _matches(keywords, text)]
    accounts = (
        []
        if asked.costs_only
        else [
            a for a, account in lists.accounts.items() if _matches(keywords, account_text(account))
        ]
    )
    goals = [
        a
        for a in accounts
        if digest.goal_amount(goal=lists.accounts[a].get("savings_goal")) is not None
    ]
    plain = [a for a in accounts if a not in goals]
    notes = []
    lenders = [name for name in lists.lenders if name in payees or name in shops]
    if lenders:
        # What the data can say about a private loan: what it repaid and the standing order.
        payees = list(dict.fromkeys([*lenders, *payees]))
        shops = list(dict.fromkeys([*lenders, *shops]))
        notes.append(DroppedTile(title="What is left of the loan", reason=LOAN_UNKNOWN))
    tiles: list[TileChoice] = []
    if asked.open_bills:
        tiles += [TileChoice(template="bill", args={"payment_id": p}) for p in lists.payments][
            :REQUEST_BILLS
        ]
        if bills is not None:
            tiles.append(TileChoice(signal=bills.id))
    tiles += [TileChoice(signal=findings[label].id) for label in found]
    goal_tiles = [
        TileChoice(
            template="savings_goal",
            args={"account_id": a},
            title=asked.goal_title if len(goals) == 1 else None,
        )
        for a in goals
    ]
    # A request about a goal is answered by the goal, unless it is about the mortgage.
    mortgage = any(findings[label].template == "mortgage" for label in found)
    tiles = tiles + goal_tiles if mortgage else goal_tiles + tiles
    if lenders:
        tiles.append(
            TileChoice(
                template="monthly_spending",
                args={"merchants": shops[:6], "months": 12},
                title="Repaid each month",
            )
        )
    costs: list[TileChoice] = []
    # The same payees as a list and as bars per month show one stream twice; the list stays.
    shops = shops if lenders else [name for name in shops if name not in payees]
    named = asked.name[:1].lower() + asked.name[1:] if asked.name.startswith("The ") else asked.name
    each_month = f"What {named} costs" if asked.costs_only else f"{asked.name} each month"
    if asked.name.casefold().startswith("what "):
        each_month = asked.name
    if len(each_month) > TITLE_SHORT or not asked.name:
        each_month = "Each month"
    if shops and not lenders:
        costs.append(
            TileChoice(
                template="monthly_spending",
                args={"merchants": shops[:6], "months": 12},
                title=each_month,
            )
        )
    if payees:
        costs.append(
            TileChoice(
                template="regular_payments",
                args={"payees": payees[:8]},
                title=asked.payees_title or asked.name,
            )
        )
    # A question about cost opens on what it cost; otherwise the goal or finding stays first.
    tiles = costs + tiles if asked.costs_only else tiles + costs

    # A decision about the mortgage is not about the house's single bills.
    if not asked.open_bills and not mortgage:
        tiles += [TileChoice(template="bill", args={"payment_id": p}) for p in payments][
            :REQUEST_BILLS
        ]
    # Accounts without a goal only when nothing more specific was found.
    if plain and not tiles:
        tiles.append(TileChoice(template="account_balances", args={"account_ids": plain[:6]}))
    return PlanAnswer(
        kind="",
        # What the board was looked up by, so the customer sees why these tiles.
        evidence=[f"Looked for: {', '.join(keywords)}"] if keywords else [],
        question=request,
        boards=[BoardChoice(name=asked.name, tiles=tiles)],
        ideas=[],
        notes=notes,
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


def _chf(value: Any) -> str:
    return f"CHF {digest.chf(value)}"


def idea_text(signal: Signal, payload: AnyPayload) -> str:
    """An idea card's sentence: one short line about one thing, figures from the payload."""
    figure = _chf(payload.figure_chf)
    match payload:
        case RegularPaymentsPayload() if signal.kind == "instalments":
            row = payload.rows[0]
            return (
                f"The next instalment to {row.payee} is due on {row.next_due:%d.%m.}, "
                f"{_chf(row.amount_chf)}."
            )
        case RegularPaymentsPayload() if signal.kind == "private_loan":
            return f"You pay back {figure} a month to {payload.rows[0].payee}."
        case RegularPaymentsPayload():
            return f"Your {len(payload.rows)} largest monthly payments come to {figure}."
        case SavingsGoalPayload():
            return f"{payload.account_name} holds {figure} for {payload.goal_text}."
        case BillPayload():
            return f"{payload.payee} is due on {payload.due:%d.%m.}: {figure}."
        case CardBillPayload():
            return f"The {payload.card_name} bill is {figure}."
        case ExpectedIncomePayload():
            return f"{payload.counterparty} sends about {figure} a month."
        case Pillar3aPayload():
            return f"{figure} is still open for pillar 3a this year."
        case SecuritiesPayload():
            return f"The depot is worth {figure}."
        case AccountBalancesPayload():
            return f"Your {len(payload.rows)} savings accounts hold {figure} together."
    return signal.text
