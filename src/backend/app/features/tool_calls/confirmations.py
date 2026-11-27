import asyncio
from dataclasses import dataclass
from uuid import UUID

from app.features.tool_calls.schemas import RequestToolCallConfirmationCreate


@dataclass(frozen=True)
class WaitingCall:
    tool_name: str
    answer: asyncio.Future[RequestToolCallConfirmationCreate]


# ponytail: held in this process, so one worker; a database row once there are several
class Confirmations:
    """The tool calls that wait for the customer's yes or no."""

    def __init__(self) -> None:
        self.waiting: dict[tuple[UUID, UUID], WaitingCall] = {}

    async def wait(
        self, conversation_id: UUID, tool_call_id: UUID, tool_name: str, timeout_seconds: float
    ) -> RequestToolCallConfirmationCreate:
        """The customer's answer; no answer in time counts as no."""
        key = (conversation_id, tool_call_id)
        answer = asyncio.get_running_loop().create_future()
        self.waiting[key] = WaitingCall(tool_name=tool_name, answer=answer)
        try:
            async with asyncio.timeout(timeout_seconds):
                return await answer
        except TimeoutError:
            return RequestToolCallConfirmationCreate(is_allowed=False)
        finally:
            del self.waiting[key]

    def get_tool_name(self, conversation_id: UUID, tool_call_id: UUID) -> str | None:
        """The tool of the call that waits for an answer; None when no such call does."""
        call = self.waiting.get((conversation_id, tool_call_id))
        if call is None or call.answer.done():
            return None
        return call.tool_name

    def answer(
        self, conversation_id: UUID, tool_call_id: UUID, data: RequestToolCallConfirmationCreate
    ) -> None:
        """Pass the answer on to the call, which `get_tool_name` found waiting."""
        self.waiting[(conversation_id, tool_call_id)].answer.set_result(data)
