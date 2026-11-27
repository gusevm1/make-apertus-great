import re
from collections.abc import AsyncIterator
from uuid import UUID

import anyio

from app.core.errors import BadRequestError, NotFoundError
from app.core.provenance import Provenance
from app.core.streaming import DoneEvent, StreamEvent
from app.features.conversations.prompts import chat_prompt
from app.features.conversations.repository import ConversationRepository, MessageRepository
from app.features.conversations.schemas import (
    Conversation,
    Message,
    RequestConversationCreate,
    RequestConversationUpdate,
    RequestMessageCreate,
)
from app.features.tool_calls.service import ToolCallService

HISTORY_LIMIT = 20
LINK_TARGET = re.compile(r"\]\([^)]*\)")
LIST_NUMBER = re.compile(r"^\s*\d+[.)]\s", re.MULTILINE)


def is_quoted(text: str, content: str) -> bool:
    """Whether `text`, selected from the rendered Markdown, is a passage of `content`."""
    # A selection can start and end inside a word, so its ends need no word boundary.
    return _words(text=text) in _words(text=content)


def _words(text: str) -> str:
    # ponytail: words only, so Markdown marks drop out; code fences and entities still differ
    text = LIST_NUMBER.sub(" ", LINK_TARGET.sub(" ", text))
    return " ".join(re.findall(r"[^\W_]+", text.casefold()))


class ConversationService:
    def __init__(
        self,
        conversations: ConversationRepository,
        messages: MessageRepository,
        tool_calls: ToolCallService,
    ) -> None:
        self.conversations = conversations
        self.messages = messages
        self.tool_calls = tool_calls

    async def create_conversation(
        self, data: RequestConversationCreate, owner_id: UUID
    ) -> Conversation:
        """Create an empty conversation owned by the user."""
        return await self.conversations.create(data=data, owner_id=owner_id)

    async def list_conversations(
        self, owner_id: UUID, sort: str | None = None
    ) -> list[Conversation]:
        """List the user's conversations."""
        return await self.conversations.list(sort=sort, owner_id=owner_id)

    async def get_conversation(self, conversation_id: UUID, owner_id: UUID) -> Conversation:
        """Return the user's conversation; someone else's counts as not found."""
        conversation = await self.conversations.get_owned(
            conversation_id=conversation_id, owner_id=owner_id
        )
        if conversation is None:
            raise NotFoundError("Conversation not found")
        return conversation

    async def update_conversation(
        self, conversation_id: UUID, data: RequestConversationUpdate
    ) -> Conversation:
        """Change the fields that were sent."""
        conversation = await self.conversations.update(entity_id=conversation_id, data=data)
        if conversation is None:
            raise NotFoundError("Conversation not found")
        return conversation

    async def delete_conversation(self, conversation_id: UUID) -> None:
        """Delete the conversation and, through the FK cascade, its messages."""
        if not await self.conversations.delete(entity_id=conversation_id):
            raise NotFoundError("Conversation not found")

    async def list_messages(self, conversation_id: UUID, sort: str | None = None) -> list[Message]:
        """List a conversation's messages, oldest first by default."""
        return await self.messages.list(sort=sort, conversation_id=conversation_id)

    async def create_message(self, conversation_id: UUID, data: RequestMessageCreate) -> Message:
        """Store the user's message and return the stored reply, which may have used tools."""
        history = await self._add_user_message(conversation_id=conversation_id, data=data)
        try:
            messages = chat_prompt(history=history, page=data.page)
            content, provenance = await self.tool_calls.create_answer(
                conversation_id=conversation_id,
                message_id=history[-1].id,
                messages=messages,
            )
        except Exception:
            await self.messages.delete(entity_id=history[-1].id)
            raise
        return await self._store_reply(
            conversation_id=conversation_id, content=content, provenance=provenance
        )

    async def stream_message(
        self, conversation_id: UUID, data: RequestMessageCreate
    ) -> AsyncIterator[StreamEvent[Message]]:
        """Like `create_message`, but yields the turn's events, then the stored reply."""
        history = await self._add_user_message(conversation_id=conversation_id, data=data)
        messages = chat_prompt(history=history, page=data.page)
        events = self.tool_calls.stream_answer(
            conversation_id=conversation_id,
            message_id=history[-1].id,
            messages=messages,
        )
        is_stored = False
        try:
            async for event in events:
                if not isinstance(event, DoneEvent):
                    yield event
                    continue
                content, provenance = event.result
            reply = await self._store_reply(
                conversation_id=conversation_id, content=content, provenance=provenance
            )
            is_stored = True
        finally:
            # Also when the page closes mid-answer, which cancels the turn: a question stored
            # without its reply would put two user turns in a row into the next prompt.
            if not is_stored:
                with anyio.CancelScope(shield=True):
                    await self.messages.delete(entity_id=history[-1].id)
        yield DoneEvent(result=reply)

    async def _add_user_message(
        self, conversation_id: UUID, data: RequestMessageCreate
    ) -> list[Message]:
        """Store the user's message; returns the recent history ending with it."""
        # Read first: the write's commit then leaves no transaction open across the LLM call.
        history = await self.messages.list_recent(
            conversation_id=conversation_id, limit=HISTORY_LIMIT - 1
        )
        await self._check_quotes(conversation_id=conversation_id, data=data)
        message = await self.messages.create(
            conversation_id=conversation_id,
            role="user",
            content=data.content,
            quotes=[quote.model_dump(mode="json") for quote in data.quotes],
        )
        return [*history, message]

    async def _check_quotes(self, conversation_id: UUID, data: RequestMessageCreate) -> None:
        if not data.quotes:
            return
        contents = await self.messages.list_contents(
            conversation_id=conversation_id,
            message_ids=[quote.message_id for quote in data.quotes],
        )
        for quote in data.quotes:
            content = contents.get(quote.message_id)
            if content is None:
                raise NotFoundError("Quoted message not found in this conversation")
            if not is_quoted(text=quote.text, content=content):
                raise BadRequestError("Quoted text not found in the quoted message")

    async def _store_reply(
        self, conversation_id: UUID, content: str, provenance: Provenance
    ) -> Message:
        return await self.messages.create(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            provenance=provenance.model_dump(),
        )
