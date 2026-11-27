import json
import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID

from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.errors import AppError, ErrorResponse
from app.core.tools import SheetLine

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TokenEvent:
    text: str


@dataclass(frozen=True)
class PlanningEvent:
    round: int


# The answer is written and its figures are being checked before it shows.
@dataclass(frozen=True)
class CheckingEvent:
    pass


@dataclass(frozen=True)
class ToolCallEvent:
    id: UUID
    tool_name: str
    title: str
    icon: str
    arguments: dict[str, Any]
    reason: str
    round: int
    plan: str
    # Set while the call waits for the customer to allow it.
    confirmation: str | None
    # What the sheet lists while it waits; None: the raw arguments.
    lines: list[SheetLine] | None


@dataclass(frozen=True)
class ToolResultEvent:
    id: UUID
    result: dict[str, Any] | None
    error: str | None


@dataclass(frozen=True)
class DoneEvent[T]:
    result: T


type StreamEvent[T] = (
    TokenEvent | PlanningEvent | CheckingEvent | ToolCallEvent | ToolResultEvent | DoneEvent[T]
)


def _format(event: str, payload: str) -> str:
    return f"event: {event}\ndata: {payload}\n\n"


def _event(
    event: str, data: PlanningEvent | CheckingEvent | ToolCallEvent | ToolResultEvent
) -> str:
    return _format(event=event, payload=json.dumps(asdict(data), default=str))


def _error(body: ErrorResponse) -> str:
    return _format(event="error", payload=body.model_dump_json(exclude_none=True))


def sse_response[T](
    events: AsyncIterator[StreamEvent[T]], to_response: Callable[[T], BaseModel]
) -> StreamingResponse:
    """Turn a service's events into SSE: planning, tools, checking, token… then done or error."""

    async def body() -> AsyncIterator[str]:
        try:
            async for event in events:
                if isinstance(event, TokenEvent):
                    yield _format(event="token", payload=json.dumps({"text": event.text}))
                elif isinstance(event, PlanningEvent):
                    yield _event(event="planning", data=event)
                elif isinstance(event, CheckingEvent):
                    yield _event(event="checking", data=event)
                elif isinstance(event, ToolCallEvent):
                    yield _event(event="tool_call", data=event)
                elif isinstance(event, ToolResultEvent):
                    yield _event(event="tool_result", data=event)
                else:
                    yield _format(event="done", payload=to_response(event.result).model_dump_json())
        except AppError as exc:
            yield _error(body=exc.to_response())
        except Exception:
            logger.exception("Unhandled error during stream")
            yield _error(body=ErrorResponse(error="internal_error", message="Stream failed"))

    return StreamingResponse(body(), media_type="text/event-stream")
