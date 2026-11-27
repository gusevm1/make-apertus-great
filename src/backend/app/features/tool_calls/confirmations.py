import asyncio
from uuid import UUID


# ponytail: held in this process, so one worker; a database row once there are several
class Confirmations:
    """The tool calls that wait for the customer's yes or no."""

    def __init__(self) -> None:
        self.waiting: dict[tuple[UUID, UUID], asyncio.Future[bool]] = {}

    async def wait(self, conversation_id: UUID, tool_call_id: UUID, timeout_seconds: float) -> bool:
        """The customer's answer; no answer in time counts as no."""
        key = (conversation_id, tool_call_id)
        self.waiting[key] = asyncio.get_running_loop().create_future()
        try:
            async with asyncio.timeout(timeout_seconds):
                return await self.waiting[key]
        except TimeoutError:
            return False
        finally:
            del self.waiting[key]

    def answer(self, conversation_id: UUID, tool_call_id: UUID, is_allowed: bool) -> bool:
        """Pass the answer on; False when no such call waits for one."""
        answer = self.waiting.get((conversation_id, tool_call_id))
        if answer is None or answer.done():
            return False
        answer.set_result(is_allowed)
        return True
