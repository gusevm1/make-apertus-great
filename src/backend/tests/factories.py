from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import owner_id
from app.features.conversations.repository import ConversationRepository, MessageRepository
from app.features.conversations.schemas import Conversation, Message
from app.features.tool_calls.repository import ToolCallRepository
from app.features.tool_calls.schemas import ToolCall

DEMO_USER_ID = owner_id(customer_id="CUST-001")


async def make_conversation(session: AsyncSession, **overrides: Any) -> Conversation:
    fields = {"owner_id": DEMO_USER_ID, "title": "Test conversation", **overrides}
    return await ConversationRepository(session=session).create(**fields)


async def make_message(session: AsyncSession, conversation_id: UUID, **overrides: Any) -> Message:
    fields = {"role": "user", "content": "Hello", **overrides}
    return await MessageRepository(session=session).create(
        conversation_id=conversation_id, **fields
    )


async def make_tool_call(
    session: AsyncSession, conversation_id: UUID, message_id: UUID, **overrides: Any
) -> ToolCall:
    fields = {
        "position": 0,
        "reason": "Need the page.",
        "tool_name": "lookup",
        "arguments": {},
        "result": {"text": "Page about Zurich"},
        **overrides,
    }
    return await ToolCallRepository(session=session).create(
        conversation_id=conversation_id, message_id=message_id, **fields
    )
