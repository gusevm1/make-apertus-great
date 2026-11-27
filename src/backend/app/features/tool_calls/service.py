import logging
import time
from collections.abc import AsyncIterator
from datetime import date
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.clients.apertus import ApertusClient, Model
from app.clients.apertus import Message as LLMMessage
from app.core.errors import AppError, NotFoundError, UpstreamError
from app.core.provenance import Check, Provenance, Source
from app.core.streaming import (
    DoneEvent,
    PlanningEvent,
    StreamEvent,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from app.core.tools import Tool, Turn, TurnResult
from app.features.tool_calls.confirmations import Confirmations
from app.features.tool_calls.prompts import (
    ToolRound,
    answer_prompt,
    dated_prompt,
    decision_prompt,
)
from app.features.tool_calls.repository import ToolCallRepository
from app.features.tool_calls.schemas import (
    RequestToolCallConfirmationCreate,
    ToolCall,
    ToolDecision,
    ToolRequest,
)

MAX_TOOL_CALLS = 8
MAX_TOOL_ROUNDS = 4
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
        # The e-banking's date, which the demo data ends on; the server clock may differ.
        self.today = today

    async def create_answer(
        self, conversation_id: UUID, message_id: UUID, messages: list[LLMMessage]
    ) -> tuple[str, Provenance]:
        """Answer the messages, calling tools first when the model asks for them."""
        started = time.perf_counter()
        # Nobody reads this turn while it runs, so a call that needs the customer's yes gets none.
        steps = self._call_tools(
            conversation_id=conversation_id,
            message_id=message_id,
            messages=messages,
            can_ask=False,
        )
        calls = [step async for step in steps if isinstance(step, ToolCall)]
        # Streamed, so the timeout counts the wait per chunk, not the whole answer.
        stream = self.apertus.stream_chat(
            messages=answer_prompt(
                messages=dated_prompt(messages=messages, today=self.today), calls=calls
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
        self, conversation_id: UUID, message_id: UUID, messages: list[LLMMessage]
    ) -> AsyncIterator[StreamEvent[tuple[str, Provenance]]]:
        """Like `create_answer`, but yields each tool call, the answer's tokens, then the answer."""
        started = time.perf_counter()
        calls: list[ToolCall] = []
        async for step in self._call_tools(
            conversation_id=conversation_id,
            message_id=message_id,
            messages=messages,
            can_ask=True,
        ):
            if not isinstance(step, ToolCall):
                yield step
                continue
            calls.append(step)
            yield ToolResultEvent(id=step.id, result=step.result, error=step.error)
        stream = self.apertus.stream_chat(
            messages=answer_prompt(
                messages=dated_prompt(messages=messages, today=self.today), calls=calls
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
        """Pass the customer's yes or no to the call that waits for it."""
        is_waiting = self.confirmations.answer(
            conversation_id=conversation_id, tool_call_id=tool_call_id, is_allowed=data.is_allowed
        )
        if not is_waiting:
            raise NotFoundError("No tool call waits for this confirmation")

    async def _call_tools(
        self, conversation_id: UUID, message_id: UUID, messages: list[LLMMessage], can_ask: bool
    ) -> AsyncIterator[PlanningEvent | ToolCallEvent | ToolCall]:
        """Run the requested calls round by round; yields each round, each call's start and end."""
        calls: list[ToolCall] = []
        rounds: list[ToolRound] = []
        # After a no, the turn does not ask for the same tool again.
        refused: set[str] = set()
        for round_number in range(MAX_TOOL_ROUNDS):
            yield PlanningEvent(round=round_number)
            result = await self.apertus.structured(
                messages=decision_prompt(
                    messages=messages,
                    rounds=rounds,
                    tools=list(self.tools.values()),
                    today=self.today,
                ),
                schema=ToolDecision,
                model=DECISION_MODEL,
                purpose=DECISION_PURPOSE,
            )
            decision = result.content
            decision.plan = SwissSpelling().feed(text=decision.plan)
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
                if request.tool == "" or _already_called(calls=calls, request=request):
                    continue
                call_id = uuid4()
                title, icon = self._label(name=request.tool)
                confirmation = self._confirmation(request=request)
                is_asked = confirmation is not None and can_ask and request.tool not in refused
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
                )
                is_allowed = confirmation is None or (
                    is_asked
                    and await self.confirmations.wait(
                        conversation_id=conversation_id,
                        tool_call_id=call_id,
                        timeout_seconds=CONFIRMATION_TIMEOUT_SECONDS,
                    )
                )
                if is_allowed:
                    output, error = await self._run_tool(
                        call_id=call_id,
                        name=request.tool,
                        arguments=request.arguments,
                        turn=_turn(conversation_id=conversation_id, calls=calls),
                    )
                else:
                    refused.add(request.tool)
                    output, error = None, NOT_ALLOWED
                call = await self.tool_calls.create(
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
                    arguments=request.arguments,
                    result=output,
                    error=error,
                    provenance=Provenance(
                        model=result.model, latency_ms=result.latency_ms
                    ).model_dump(),
                )
                calls.append(call)
                round_calls.append(call)
                yield call
            # A round without a new call means the model has what it needs, or is stuck.
            if not round_calls or len(calls) == MAX_TOOL_CALLS:
                break
            rounds.append((decision, round_calls))

    def _confirmation(self, request: ToolRequest) -> str | None:
        """What the customer has to allow first; a call that cannot run needs no answer."""
        tool = self.tools.get(request.tool)
        if tool is None or tool.confirmation is None:
            return None
        try:
            tool.args_schema.model_validate(request.arguments)
        except ValidationError:
            return None
        return tool.confirmation

    def _builds_on_turn(self, name: str) -> bool:
        tool = self.tools.get(name)
        return tool is not None and tool.turn_handler is not None

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
            problems = "; ".join(
                f"{'.'.join(str(part) for part in problem['loc'])}: {problem['msg']}"
                for problem in exc.errors()
            )
            return None, f"Invalid arguments. {problems}"
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


def _turn(conversation_id: UUID, calls: list[ToolCall]) -> Turn:
    results = [
        TurnResult(tool_call_id=call.id, tool_name=call.tool_name, result=call.result)
        for call in calls
        if call.result is not None
    ]
    return Turn(conversation_id=conversation_id, results=results)


def _merge_identical(requests: list[ToolRequest]) -> list[ToolRequest]:
    """One request per distinct call; the reasons of identical ones are joined."""
    merged: dict[str, ToolRequest] = {}
    for request in requests:
        key = request.model_dump_json(exclude={"reason"})
        same = merged.get(key)
        reason = request.reason if same is None else f"{same.reason}; {request.reason}"
        merged[key] = request.model_copy(update={"reason": reason})
    return list(merged.values())


def _already_called(calls: list[ToolCall], request: ToolRequest) -> bool:
    return any(
        call.tool_name == request.tool and call.arguments == request.arguments for call in calls
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
