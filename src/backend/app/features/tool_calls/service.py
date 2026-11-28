import logging
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
        # Streamed, so the timeout counts the wait per chunk, not the whole answer.
        stream = self.apertus.stream_chat(
            messages=answer_prompt(
                messages=dated_prompt(messages=messages, today=self.today),
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
        return SwissSpelling().feed(text=stream.result.content), provenance

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
        stream = self.apertus.stream_chat(
            messages=answer_prompt(
                messages=dated_prompt(messages=messages, today=self.today),
                calls=calls,
                tools=list(self.tools.values()),
                scoped=scope is not None,
            ),
            model=ANSWER_MODEL,
            purpose=ANSWER_PURPOSE,
        )
        spelling = SwissSpelling()
        async for text in stream:
            yield TokenEvent(text=spelling.feed(text=text))
        if stream.result is None:
            raise UpstreamError("Apertus stream ended without a result")
        provenance = self._provenance(model=stream.result.model, started=started, calls=calls)
        yield DoneEvent(result=(SwissSpelling().feed(text=stream.result.content), provenance))

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
            scoped = [*scope.tools, *(self.tools[name] for name in SCOPE_SHARED if name in self.tools)]
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
                return
            # The full decision reads the question as before; the board only distracted it.
            messages = _without(messages=messages, text=scope.context)
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
            if not round_calls or len(calls) == MAX_TOOL_CALLS or getattr(decision, "look_up", False):
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
        return output.model_dump(mode="json"), None

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


def _without(messages: list[LLMMessage], text: str) -> list[LLMMessage]:
    *earlier, last = messages
    content = last["content"]
    if not isinstance(content, str):
        return messages
    return [*earlier, {**last, "content": content.replace(text, "")}]


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
