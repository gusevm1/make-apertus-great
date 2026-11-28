import logging
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import date
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError
from pydantic_core import ErrorDetails

from app.clients.apertus import ApertusClient, LLMResult, Model
from app.clients.apertus import Message as LLMMessage
from app.core.errors import AppError, BadRequestError, NotFoundError, UpstreamError
from app.core.provenance import Check, Provenance, Source
from app.core.streaming import (
    DoneEvent,
    PlanningEvent,
    StreamEvent,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from app.core.tools import SheetLine, Tool, Turn, TurnResult, TurnScope
from app.features.tool_calls.confirmations import Confirmations
from app.features.tool_calls.prompts import (
    ToolRound,
    answer_prompt,
    dated_prompt,
    decision_prompt,
    scoped_decision_prompt,
)
from app.features.tool_calls.repository import ToolCallRepository
from app.features.tool_calls.schemas import (
    RequestToolCallConfirmationCreate,
    ToolCall,
    ToolDecision,
    ToolRequest,
    decision_schema,
    scoped_decision_schema,
)
from app.features.tool_calls.totals import total_sentence

MAX_TOOL_CALLS = 8
MAX_TOOL_ROUNDS = 4
# A board change rarely needs a second round, unless the first call was wrong.
MAX_SCOPED_ROUNDS = 2
SCOPED_PURPOSE = "scoped_decision"
# Tools of the full set that a scoped decision may call too.
SCOPE_SHARED = ("propose_context_entry",)
DECISION_MODEL = Model.SMART
DECISION_PURPOSE = "tool_decision"
ANSWER_MODEL = Model.SMART
ANSWER_PURPOSE = "answer"
# The server's own calls when the board decision made none for a question its tiles answer.
PROPOSE_TOOL = "propose_context_entry"
FALLBACK_PLAN = "The tiles on the board answer this question."
FALLBACK_REASON = "the question"
FALLBACK_MODEL = "server"
# ponytail: board edits by name; their summaries under the answer say it all, so no answer is
# written. A Tool flag once a second feature has such tools.
SILENT_EDITS = {"rename_tile", "move_tile", "remove_tile", "change_tile", "rename_board"}
EDIT_DONE = "Done."
UNKNOWN_TOOL_ICON = "circle-help"
TOOL_FAILED = "The tool failed."
NOT_ALLOWED = "The customer has not allowed this call. Continue without it."
# Shorter than the 300 seconds nginx keeps a silent stream open.
CONFIRMATION_TIMEOUT_SECONDS = 120
# The model writes ß despite the prompt; Swiss German always writes ss.
SHARP_S = {"ß": "ss", "ẞ": "SS"}
# ponytail: models mix marks („…"), so any closing mark ends the open quote; a line ends all
OPENING_QUOTES = "«‹„"
CLOSING_QUOTES = "»›”"
EITHER_QUOTES = '“"'
# Thousands written with a space of any width or a comma, which Swiss amounts write as 1'050.00.
_SEPARATORS = " \u00a0\u2009\u202f,"
_AMOUNT = re.compile(
    rf"(?<![\d'\u2019.,])(?<!\d[{_SEPARATORS}])"
    rf"(\d{{1,3}}(?:([{_SEPARATORS}])\d{{3}})(?:\2\d{{3}})*)(\.\d{{1,2}}(?!\d))?(?![\d'\u2019])"
)
_CURRENCY_BEFORE = re.compile(r"(?:CHF|Fr\.|EUR|USD|\u20ac|\$)\s?-?$")
_CURRENCY_AFTER = re.compile(r"^\s?(?:CHF|Franken|francs?)\b", re.IGNORECASE)
# A number may still go on: held back until the text after it arrives.
_OPEN_NUMBER = re.compile(rf"\d[\d.'\u2019{_SEPARATORS}]*$")
_CONTEXT_CHARS = 8
# Beside a board: a dash between parts of a sentence becomes a comma, a day drops this year.
_SENTENCE_DASH = re.compile(r"\s+[—–]\s+|\s*—\s*")
_DAY_WITH_YEAR = re.compile(r"\b(\d{1,2})\. ?(\d{1,2})\.(?: ?(\d{4})\b)?")
# Words about our own machinery that an answer beside a board never needs.
_BOARD_WORDS = re.compile(r",? as (?:stated|shown|given) in (?:the|its) meaning", re.I)
# A first sentence that only says what changed, such as: Done, "X" has been removed.
_DONE_SENTENCE = re.compile(
    r"^\s*(?:Done\b[.,:!]?\s*)?[^.!?\n]*\b(?:removed|renamed|moved|added)\b[^.!?\n]*[.!]\s*",
    re.I,
)
# ponytail: only the safe cases of "tile"; any other sentence with it stays as it is
_TILE_CLAUSE = re.compile(r",?\s*(?:according to|as) the tile[’']s description(?: says)?,?", re.I)
_QUOTED_TILE = re.compile(r"\b[Tt]he (?:new )?([“\"][^”\"\n]+[”\"]) tile\b")
_YOUR_TILE = re.compile(r"\b([Yy]our(?: new)?) ([“\"][^”\"\n]+[”\"]) tile\b")
_SENTENCE_START = re.compile(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ])")
# A last sentence keeps its place when it holds a figure, a name or advice.
_FACT = re.compile(r"\d|\b(?:payee|tell me|let me|ask|you could|you can)\b", re.I)
_DAY_THEN_STOP = re.compile(r"(\b\d{1,2}\.\d{1,2}\.)\.")
_OPEN_DASH = re.compile(r"[\s—–]+$|\b\d{1,2}\.?\s+[^\W\d]*\s*\d{0,3}$")
_MONTH_NUMBERS = {
    name: number
    for names in (
        "January February March April May June July August September October November December",
        "Januar Februar März April Mai Juni Juli August September Oktober November Dezember",
    )
    for number, name in enumerate(names.split(), start=1)
}
_DAY_MONTH_YEAR = re.compile(rf"\b(\d{{1,2}})\.?\s+({'|'.join(_MONTH_NUMBERS)})(?:\s+(\d{{4}}))?\b")
# A tile's index in the board block, such as T2 in: T2 "Bills due before the salary".
TILE_INDEX = re.compile(r"\bT\d+ (?=\")")
_CURRENCY_SPACE = re.compile(r"CHF[\u00a0\u202f\u2009]")
_TYPOGRAPHIC_THOUSANDS = re.compile(r"(?<=\d)\u2019(?=\d{3}(?!\d))")


logger = logging.getLogger(__name__)


class ToolCallService:
    def __init__(
        self,
        tool_calls: ToolCallRepository,
        apertus: ApertusClient,
        tools: list[Tool[Any]],
        today: date,
        confirmations: Confirmations,
    ) -> None:
        self.tool_calls = tool_calls
        self.apertus = apertus
        self.confirmations = confirmations
        self.tools = {tool.name: tool for tool in tools}
        self.decision_schema = decision_schema(tools=tools)
        # The e-banking's date, which the demo data ends on; the server clock may differ.
        self.today = today

    async def create_answer(
        self,
        conversation_id: UUID,
        message_id: UUID,
        messages: list[LLMMessage],
        scope: TurnScope | None = None,
    ) -> tuple[str, Provenance]:
        """Answer the messages, calling tools first when the model asks for them."""
        started = time.perf_counter()
        # Nobody reads this turn while it runs, so a call that needs the customer's yes gets none.
        steps = self._call_tools(
            conversation_id=conversation_id,
            message_id=message_id,
            messages=messages,
            can_ask=False,
            scope=scope,
        )
        calls = [step async for step in steps if isinstance(step, ToolCall)]
        if _is_silent_edit(calls=calls):
            model = _decision_model(calls=calls)
            return EDIT_DONE, self._provenance(model=model, started=started, calls=calls)
        # Streamed, so the timeout counts the wait per chunk, not the whole answer.
        stream = self.apertus.stream_chat(
            messages=answer_prompt(
                messages=dated_prompt(
                    messages=_answer_messages(messages=messages, scope=scope, calls=calls),
                    today=self.today,
                ),
                calls=calls,
                tools=list(self.tools.values()),
                scoped=scope is not None,
            ),
            model=ANSWER_MODEL,
            purpose=ANSWER_PURPOSE,
        )
        async for _ in stream:
            pass
        if stream.result is None:
            raise UpstreamError("Apertus stream ended without a result")
        provenance = self._provenance(model=stream.result.model, started=started, calls=calls)
        content = swiss_text(text=stream.result.content)
        if scope is not None:
            content = without_empty_end(
                text=Paragraphs(is_on=True).feed(
                    text=board_style(text=content, year=self.today.year)
                )
            )
        return content, provenance

    async def stream_answer(
        self,
        conversation_id: UUID,
        message_id: UUID,
        messages: list[LLMMessage],
        scope: TurnScope | None = None,
    ) -> AsyncIterator[StreamEvent[tuple[str, Provenance]]]:
        """Like `create_answer`, but yields each tool call, the answer's tokens, then the answer."""
        started = time.perf_counter()
        calls: list[ToolCall] = []
        async for step in self._call_tools(
            conversation_id=conversation_id,
            message_id=message_id,
            messages=messages,
            can_ask=True,
            scope=scope,
        ):
            if not isinstance(step, ToolCall):
                yield step
                continue
            calls.append(step)
            yield ToolResultEvent(
                id=step.id, arguments=step.arguments, result=step.result, error=step.error
            )
        if _is_silent_edit(calls=calls):
            yield TokenEvent(text=EDIT_DONE)
            provenance = self._provenance(
                model=_decision_model(calls=calls), started=started, calls=calls
            )
            yield DoneEvent(result=(EDIT_DONE, provenance))
            return
        stream = self.apertus.stream_chat(
            messages=answer_prompt(
                messages=dated_prompt(
                    messages=_answer_messages(messages=messages, scope=scope, calls=calls),
                    today=self.today,
                ),
                calls=calls,
                tools=list(self.tools.values()),
                scoped=scope is not None,
            ),
            model=ANSWER_MODEL,
            purpose=ANSWER_PURPOSE,
        )
        spelling = SwissSpelling()
        numbers = SwissFigures()
        paragraphs = Paragraphs(is_on=scope is not None)
        style = BoardStyle(year=None if scope is None else self.today.year)
        async for text in stream:
            spelled = numbers.feed(text=spelling.feed(text=text))
            yield TokenEvent(text=paragraphs.feed(text=style.feed(text=spelled)))
        rest = paragraphs.feed(text=style.feed(text=numbers.flush()) + style.flush())
        if rest != "":
            yield TokenEvent(text=rest)
        if stream.result is None:
            raise UpstreamError("Apertus stream ended without a result")
        provenance = self._provenance(model=stream.result.model, started=started, calls=calls)
        content = swiss_text(text=stream.result.content)
        if scope is not None:
            content = without_empty_end(
                text=Paragraphs(is_on=True).feed(
                    text=board_style(text=content, year=self.today.year)
                )
            )
        yield DoneEvent(result=(content, provenance))

    async def list_tool_calls(self, conversation_id: UUID) -> list[ToolCall]:
        """List the tool calls made in a conversation, oldest first."""
        return await self.tool_calls.list(conversation_id=conversation_id)

    def confirm_tool_call(
        self, conversation_id: UUID, tool_call_id: UUID, data: RequestToolCallConfirmationCreate
    ) -> None:
        """Pass the customer's answer, with the arguments they changed, to the call that waits."""
        tool_name = self.confirmations.get_tool_name(
            conversation_id=conversation_id, tool_call_id=tool_call_id
        )
        if tool_name is None:
            raise NotFoundError("No tool call waits for this confirmation")
        if data.is_allowed and data.arguments is not None:
            tool = self.tools[tool_name]
            if not tool.is_editable:
                raise BadRequestError("The arguments of this call cannot be changed")
            try:
                tool.args_schema.model_validate(data.arguments)
            except ValidationError as exc:
                raise BadRequestError(f"Invalid arguments. {_problems(exc=exc)}") from exc
        self.confirmations.answer(
            conversation_id=conversation_id, tool_call_id=tool_call_id, data=data
        )

    async def _call_tools(
        self,
        conversation_id: UUID,
        message_id: UUID,
        messages: list[LLMMessage],
        can_ask: bool,
        scope: TurnScope | None,
    ) -> AsyncIterator[PlanningEvent | ToolCallEvent | ToolCall]:
        """Run the requested calls round by round; yields each round, each call's start and end."""
        calls: list[ToolCall] = []
        rounds: list[ToolRound] = []
        # After a no, the turn does not ask for the same tool again.
        refused: set[str] = set()
        full = list(self.tools.values())
        first_round = 0
        if scope is not None:
            # A small decision first: most messages beside a board change it or ask about it.
            scoped = [
                *scope.tools,
                *(self.tools[name] for name in SCOPE_SHARED if name in self.tools),
            ]
            self.tools.update({tool.name: tool for tool in scope.tools})
            schema = scoped_decision_schema(tools=scoped)
            look_up = False
            try:
                async for step in self._rounds(
                    first_round=0,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    can_ask=can_ask,
                    calls=calls,
                    rounds=rounds,
                    refused=refused,
                    max_rounds=MAX_SCOPED_ROUNDS,
                    decide=lambda: self.apertus.structured(
                        messages=scoped_decision_prompt(
                            messages=messages,
                            rounds=rounds,
                            tools=scoped,
                            today=self.today,
                            guide=scope.guide,
                        ),
                        schema=schema,
                        model=DECISION_MODEL,
                        purpose=SCOPED_PURPOSE,
                    ),
                ):
                    if isinstance(step, ToolDecision):
                        look_up = look_up or getattr(step, "look_up", False)
                        continue
                    if isinstance(step, PlanningEvent):
                        first_round = step.round + 1
                    yield step
            except UpstreamError:
                # Such as invalid JSON twice: the full decision still answers the message.
                logger.exception("Scoped decision for message %s failed", message_id)
                look_up = True
            if not look_up:
                requests = (
                    _note_requests(calls=calls)
                    if calls or scope.fallback is None
                    else scope.fallback(_question(messages=messages, context=scope.context))
                )
                if not requests:
                    return
                decision = ToolDecision(
                    plan=FALLBACK_PLAN,
                    calls=[
                        ToolRequest(tool=tool, arguments=arguments, reason=FALLBACK_REASON)
                        for tool, arguments in requests
                    ],
                )
                fallback = LLMResult(
                    content=decision,
                    model=FALLBACK_MODEL,
                    latency_ms=0,
                    tokens_in=None,
                    tokens_out=None,
                )
                async for step in self._rounds(
                    first_round=first_round,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    can_ask=can_ask,
                    calls=calls,
                    rounds=rounds,
                    refused=refused,
                    max_rounds=1,
                    decide=lambda: _ready(result=fallback),
                ):
                    if not isinstance(step, ToolDecision):
                        yield step
                return
            # The full decision reads the question as before; the board only distracted it.
            messages = _replaced(messages=messages, text=scope.context, by="")
        async for step in self._rounds(
            first_round=first_round,
            conversation_id=conversation_id,
            message_id=message_id,
            can_ask=can_ask,
            calls=calls,
            rounds=rounds,
            refused=refused,
            max_rounds=MAX_TOOL_ROUNDS,
            decide=lambda: self.apertus.structured(
                messages=decision_prompt(
                    messages=messages, rounds=rounds, tools=full, today=self.today
                ),
                schema=self.decision_schema,
                model=DECISION_MODEL,
                purpose=DECISION_PURPOSE,
            ),
        ):
            if not isinstance(step, ToolDecision):
                yield step

    async def _rounds(
        self,
        conversation_id: UUID,
        message_id: UUID,
        can_ask: bool,
        calls: list[ToolCall],
        rounds: list[ToolRound],
        refused: set[str],
        first_round: int,
        max_rounds: int,
        decide: Callable[[], Awaitable[LLMResult[ToolDecision]]],
    ) -> AsyncIterator[PlanningEvent | ToolCallEvent | ToolCall | ToolDecision]:
        """One decision per round; yields it, then each call's start and end."""
        for round_number in range(first_round, first_round + max_rounds):
            yield PlanningEvent(round=round_number)
            result = await decide()
            decision = result.content
            decision.plan = SwissSpelling().feed(text=decision.plan)
            yield decision
            round_calls: list[ToolCall] = []
            # ponytail: one call after the other, asyncio.gather once a tool is slow
            # A tool that builds on the turn's results runs after the calls that fetch them.
            requests = sorted(
                _merge_identical(requests=decision.calls),
                key=lambda request: self._builds_on_turn(name=request.tool),
            )
            for request in requests:
                if len(calls) == MAX_TOOL_CALLS:
                    break
                if request.tool == "" or _already_called(
                    calls=calls,
                    request=request,
                    builds_on_turn=self._builds_on_turn(name=request.tool),
                ):
                    continue
                call_id = uuid4()
                title, icon = self._label(name=request.tool)
                confirmation = self._confirmation(name=request.tool)
                is_asked = confirmation is not None and can_ask and request.tool not in refused
                lines, refusal = (
                    await self._sheet(call_id=call_id, request=request)
                    if is_asked
                    else (None, None)
                )
                is_asked = is_asked and refusal is None
                yield ToolCallEvent(
                    id=call_id,
                    tool_name=request.tool,
                    title=title,
                    icon=icon,
                    arguments=request.arguments,
                    reason=request.reason,
                    round=round_number,
                    plan=decision.plan,
                    confirmation=confirmation if is_asked else None,
                    lines=lines,
                    is_editable=is_asked and self.tools[request.tool].is_editable,
                )
                is_allowed = confirmation is None
                arguments = request.arguments
                if is_asked:
                    answer = await self.confirmations.wait(
                        conversation_id=conversation_id,
                        tool_call_id=call_id,
                        tool_name=request.tool,
                        timeout_seconds=CONFIRMATION_TIMEOUT_SECONDS,
                    )
                    is_allowed = answer.is_allowed
                    if is_allowed and answer.arguments is not None:
                        arguments = answer.arguments
                # Stored before the tool runs, so what the tool stores can point to its call.
                await self.tool_calls.create(
                    id=call_id,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    position=len(calls),
                    round=round_number,
                    plan=decision.plan,
                    reason=request.reason,
                    tool_name=request.tool,
                    title=title,
                    icon=icon,
                    arguments=arguments,
                    result=None,
                    error=None,
                    provenance=Provenance(
                        model=result.model, latency_ms=result.latency_ms
                    ).model_dump(),
                )
                if refusal is not None:
                    output, error = None, refusal
                elif is_allowed:
                    output, error = await self._run_tool(
                        call_id=call_id,
                        name=request.tool,
                        arguments=arguments,
                        turn=_turn(conversation_id=conversation_id, call_id=call_id, calls=calls),
                    )
                else:
                    refused.add(request.tool)
                    output, error = None, NOT_ALLOWED
                call = await self.tool_calls.set_outcome(
                    call_id=call_id, result=output, error=error
                )
                calls.append(call)
                round_calls.append(call)
                yield call
            if round_calls:
                rounds.append((decision, round_calls))
            # A round without a new call means the model has what it needs, or is stuck; a
            # scoped decision that asks for a look-up hands over to the full set.
            if (
                not round_calls
                or len(calls) == MAX_TOOL_CALLS
                or getattr(decision, "look_up", False)
            ):
                break

    def find_pointers(self, calls: list[ToolCall], answer: str) -> str:
        """The lines the called tools add under this answer, each once."""
        lines: list[str] = []
        for call in calls:
            tool = self.tools.get(call.tool_name)
            if tool is None or tool.pointer is None or call.result is None:
                continue
            line = tool.pointer(call.result, answer)
            if line is not None and line not in lines:
                lines.append(line)
        return "".join(f"\n\n{line}" for line in lines)

    # Decided from the tool alone: with one, the call runs only after the customer allows it.
    def _confirmation(self, name: str) -> str | None:
        tool = self.tools.get(name)
        return None if tool is None else tool.confirmation

    def _builds_on_turn(self, name: str) -> bool:
        tool = self.tools.get(name)
        return tool is not None and tool.turn_handler is not None

    # The lines the customer reads, or why the call is refused before they are asked.
    async def _sheet(
        self, call_id: UUID, request: ToolRequest
    ) -> tuple[list[SheetLine] | None, str | None]:
        tool = self.tools[request.tool]
        try:
            args = tool.args_schema.model_validate(request.arguments)
        except ValidationError as exc:
            return None, f"Invalid arguments. {_problems(exc=exc)}"
        if tool.sheet is None:
            return None, None
        try:
            return await tool.sheet(args), None
        except AppError as exc:
            return None, str(exc)
        except Exception:
            # Such as a bank row without a field: this call fails, the turn goes on.
            logger.exception("Sheet of tool call %s to %s failed", call_id, request.tool)
            return None, TOOL_FAILED

    def _label(self, name: str) -> tuple[str, str]:
        tool = self.tools.get(name)
        if tool is None:
            return name, UNKNOWN_TOOL_ICON
        return tool.title, tool.icon

    async def _run_tool(
        self, call_id: UUID, name: str, arguments: dict[str, Any], turn: Turn
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Run the tool; a call the model got wrong comes back as an error for it to correct."""
        tool = self.tools.get(name)
        if tool is None:
            return None, f"Unknown tool '{name}'. Available: {', '.join(self.tools)}"
        try:
            args = tool.args_schema.model_validate(arguments)
        except ValidationError as exc:
            return None, f"Invalid arguments. {_problems(exc=exc)}"
        try:
            if tool.turn_handler is not None:
                output = await tool.turn_handler(args, turn)
            elif tool.handler is not None:
                output = await tool.handler(args)
            else:
                raise RuntimeError(f"Tool {name} has no handler")
        except Exception as exc:
            # A ValidationError is a ValueError, but raised inside a handler it is a bug.
            if isinstance(exc, AppError | ValueError) and not isinstance(exc, ValidationError):
                return None, str(exc)
            logger.exception("Tool call %s to %s failed", call_id, name)
            return None, TOOL_FAILED
        dumped = output.model_dump(mode="json")
        sentence = total_sentence(result=dumped, arguments=arguments)
        if sentence is not None:
            # First in the result, so a cut for length never drops it.
            dumped = {"total_sentence": sentence, **dumped}
        return dumped, None

    def _provenance(self, model: str, started: float, calls: list[ToolCall]) -> Provenance:
        succeeded = [call for call in calls if call.error is None]
        pages = {
            page["url"]: Source(id=page["url"], title=page["title"], url=page["url"])
            for call in succeeded
            if call.result is not None
            for page in call.result.get("sources", [])
        }
        check = Check(
            name="tool_calls_valid",
            passed=len(succeeded) == len(calls),
            detail=f"{len(succeeded)} of {len(calls)}",
        )
        return Provenance(
            model=model,
            latency_ms=round((time.perf_counter() - started) * 1000),
            sources=list(pages.values()),
            checks=[check] if calls else [],
        )


def _note_requests(calls: list[ToolCall]) -> list[tuple[str, dict[str, Any]]]:
    """The note a result suggested, when the decision did not propose it."""
    if any(call.tool_name == PROPOSE_TOOL for call in calls):
        return []
    notes = [
        call.result["suggested_note_text"]
        for call in calls
        if call.result is not None and call.result.get("suggested_note_text") is not None
    ]
    return [] if not notes else [(PROPOSE_TOOL, {"kind": "fact", "text": notes[0]})]


async def _ready(result: LLMResult[ToolDecision]) -> LLMResult[ToolDecision]:
    return result


def _question(messages: list[LLMMessage], context: str) -> str:
    content = messages[-1]["content"]
    if not isinstance(content, str):
        content = " ".join(part["text"] for part in content if part["type"] == "text")
    return content.replace(context, "")


def _is_silent_edit(calls: list[ToolCall]) -> bool:
    return bool(calls) and all(
        call.tool_name in SILENT_EDITS and call.error is None for call in calls
    )


def _decision_model(calls: list[ToolCall]) -> str:
    provenance = calls[-1].provenance
    return "" if provenance is None else provenance.model


def _answer_messages(
    messages: list[LLMMessage], scope: TurnScope | None, calls: list[ToolCall]
) -> list[LLMMessage]:
    # With tool results the board would pull its other tiles into the answer; they carry meanings.
    if scope is None:
        return messages
    if not calls:
        # The indexes are for the board tools; an answer that repeats them reads like code.
        return _replaced(
            messages=messages, text=scope.context, by=TILE_INDEX.sub("", scope.context)
        )
    return _replaced(messages=messages, text=scope.context, by="")


def _replaced(messages: list[LLMMessage], text: str, by: str) -> list[LLMMessage]:
    *earlier, last = messages
    content = last["content"]
    if not isinstance(content, str):
        return messages
    return [*earlier, {**last, "content": content.replace(text, by)}]


def _problems(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in problem['loc'])}: {_problem(problem=problem)}"
        for problem in exc.errors()
    )


def _problem(problem: ErrorDetails) -> str:
    # Pydantic's "Extra inputs are not permitted" made Apertus send the same argument again.
    if problem["type"] == "extra_forbidden":
        return "This tool has no such argument. Send the call again without it"
    return problem["msg"]


def _turn(conversation_id: UUID, call_id: UUID, calls: list[ToolCall]) -> Turn:
    results = [
        TurnResult(tool_call_id=call.id, tool_name=call.tool_name, result=call.result)
        for call in calls
        if call.result is not None
    ]
    return Turn(conversation_id=conversation_id, call_id=call_id, results=results)


def _merge_identical(requests: list[ToolRequest]) -> list[ToolRequest]:
    """One request per distinct call; the reasons of identical ones are joined."""
    merged: dict[str, ToolRequest] = {}
    for request in requests:
        key = request.model_dump_json(exclude={"reason"})
        same = merged.get(key)
        reason = request.reason if same is None else f"{same.reason}; {request.reason}"
        merged[key] = request.model_copy(update={"reason": reason})
    return list(merged.values())


def _already_called(calls: list[ToolCall], request: ToolRequest, builds_on_turn: bool) -> bool:
    return any(
        call.tool_name == request.tool
        and call.arguments == request.arguments
        # A tool that builds on the turn can pass the second time, once the figures are there.
        and not (builds_on_turn and call.error is not None)
        for call in calls
    )


# Writes ß as ss, except in a URL, a quote or a "> " line; takes a text in pieces, such as tokens.
class SwissSpelling:
    def __init__(self) -> None:
        self.line = ""
        self.word = ""
        self.open_quotes = 0

    def feed(self, text: str) -> str:
        return "".join(self._spell(char=char) for char in text)

    def _spell(self, char: str) -> str:
        if char == "\n":
            self.line = ""
            self.word = ""
            self.open_quotes = 0
            return char
        spelled = char
        if char in SHARP_S and not self._is_verbatim():
            spelled = SHARP_S[char]
        self.line += char
        self.word = "" if char.isspace() else self.word + char
        if char in OPENING_QUOTES or (char in EITHER_QUOTES and self.open_quotes == 0):
            self.open_quotes += 1
        elif char in CLOSING_QUOTES + EITHER_QUOTES and self.open_quotes > 0:
            self.open_quotes -= 1
        return spelled

    def _is_verbatim(self) -> bool:
        is_url = "://" in self.word or "www." in self.word
        return is_url or self.open_quotes > 0 or self.line.lstrip().startswith(">")


def swiss_figures(text: str) -> str:
    """Writes the thousands of an amount with an apostrophe: CHF 1 050.00 becomes CHF 1'050.00."""
    text = _TYPOGRAPHIC_THOUSANDS.sub("'", _CURRENCY_SPACE.sub("CHF ", text))
    return _AMOUNT.sub(lambda match: _swiss_amount(match=match, text=text), text)


def _swiss_amount(match: re.Match[str], text: str) -> str:
    before = text[max(match.start() - _CONTEXT_CHARS, 0) : match.start()]
    after = text[match.end() : match.end() + _CONTEXT_CHARS]
    is_amount = (
        match[3] is not None
        or _CURRENCY_BEFORE.search(before) is not None
        or _CURRENCY_AFTER.match(after) is not None
    )
    if not is_amount:
        return match[0]
    return match[1].replace(match[2], "'") + (match[3] or "")


# swiss_figures for a text that arrives in pieces: a number at the end waits for what follows.
class SwissFigures:
    def __init__(self) -> None:
        self.pending = ""
        self.before = ""

    def feed(self, text: str) -> str:
        text = self.pending + text
        open_number = _OPEN_NUMBER.search(text)
        cut = len(text) if open_number is None else open_number.start()
        self.pending = text[cut:]
        return self._emit(text=text[:cut])

    def flush(self) -> str:
        text, self.pending = self.pending, ""
        return self._emit(text=text)

    def _emit(self, text: str) -> str:
        # Each change keeps the length, so the context before can be cut off again.
        spelled = swiss_figures(text=self.before + text)[len(self.before) :]
        self.before = (self.before + text)[-_CONTEXT_CHARS:]
        return spelled


def swiss_text(text: str) -> str:
    """A whole answer in Swiss spelling, with Swiss amounts."""
    return swiss_figures(text=SwissSpelling().feed(text=text))


# Beside a board, a line is a paragraph unless a list item follows; leading breaks are dropped.
class Paragraphs:
    def __init__(self, is_on: bool) -> None:
        self.is_on = is_on
        self.last = ""
        self.breaks = 0

    def feed(self, text: str) -> str:
        if not self.is_on:
            return text
        return "".join(self._char(char=char) for char in text)

    def _char(self, char: str) -> str:
        if char == "\n":
            self.breaks += 1
            return ""
        if char.isspace() and self.breaks > 0:
            return ""
        out = ""
        if self.breaks > 0 and self.last != "":
            # A line break ends a paragraph, except before the next item of a list.
            out = "\n" if self.breaks == 1 and (char in "-*•" or char.isdigit()) else "\n\n"
        self.breaks = 0
        if not char.isspace():
            self.last = char
        return out + char


def board_style(text: str, year: int) -> str:
    """Beside a board: no dashes between parts of a sentence, and days of this year as 23.12."""
    text = _SENTENCE_DASH.sub(", ", text)
    text = _DAY_MONTH_YEAR.sub(lambda match: _swiss_day(match=match, year=year), text)
    text = _DAY_WITH_YEAR.sub(lambda match: _swiss_date(match=match, year=year), text)
    text = _BOARD_WORDS.sub("", text)
    text = _TILE_CLAUSE.sub("", text)
    text = _QUOTED_TILE.sub(r"\1", text)
    text = _YOUR_TILE.sub(r"\1 \2", text)
    # What was removed, renamed or moved the summaries under the answer say already.
    text = _without_done_sentence(text=text)
    # The year was the sentence's end: its full stop is the day's own.
    return _DAY_THEN_STOP.sub(r"\1", text)


# board_style for a text in pieces: a dash or a space at the end waits for what follows.
class BoardStyle:
    def __init__(self, year: int | None) -> None:
        self.year = year
        self.pending = ""

    def feed(self, text: str) -> str:
        if self.year is None:
            return text
        text = self.pending + text
        open_dash = _OPEN_DASH.search(text)
        cut = len(text) if open_dash is None else open_dash.start()
        self.pending = text[cut:]
        return board_style(text=text[:cut], year=self.year)

    def flush(self) -> str:
        text, self.pending = self.pending, ""
        return text if self.year is None else board_style(text=text, year=self.year)


def _swiss_day(match: re.Match[str], year: int) -> str:
    # "23 December 2026" becomes 23.12.; a day of another year keeps its year.
    if match[3] is not None and int(match[3]) != year:
        return match[0]
    return f"{int(match[1]):02d}.{_MONTH_NUMBERS[match[2]]:02d}."


def _swiss_date(match: re.Match[str], year: int) -> str:
    day = f"{match[1]}.{match[2]}."
    return day if match[3] is None or int(match[3]) == year else f"{day}{match[3]}"


def without_empty_end(text: str) -> str:
    """Beside a board: drop a last sentence that carries no figure, name or advice."""
    paragraphs = text.rstrip().split("\n\n")
    sentences = _SENTENCE_START.split(paragraphs[-1])
    if sum(len(_SENTENCE_START.split(part)) for part in paragraphs) < 3:
        return text
    last = sentences[-1]
    named = any(word[:1].isupper() for word in last.split()[1:])
    if _FACT.search(last) is not None or named:
        return text
    rest = " ".join(sentences[:-1])
    return "\n\n".join([*paragraphs[:-1], rest] if rest != "" else paragraphs[:-1])


def _without_done_sentence(text: str) -> str:
    # The summaries under the answer say what changed; a figure in the sentence keeps it.
    match = _DONE_SENTENCE.match(text)
    if match is None or re.search(r"\d", match[0]) is not None:
        return text
    rest = text[match.end() :]
    return text if rest.strip() == "" else rest.lstrip()
