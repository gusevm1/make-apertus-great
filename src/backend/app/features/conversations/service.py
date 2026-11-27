import json
import re
from collections.abc import AsyncIterator
from uuid import UUID

import anyio

from app.core.errors import BadRequestError, NotFoundError
from app.core.provenance import Provenance
from app.core.streaming import DoneEvent, StreamEvent, TokenEvent
from app.features.conversations.prompts import chat_prompt
from app.features.conversations.repository import ConversationRepository, MessageRepository
from app.features.conversations.schemas import (
    Conversation,
    Message,
    MessageDocument,
    RequestConversationCreate,
    RequestConversationUpdate,
    RequestMessageCreate,
)
from app.features.documents.schemas import Document
from app.features.documents.service import DocumentService
from app.features.figure_checks.service import FigureCheckService
from app.features.guardrails.schemas import Guardrail
from app.features.guardrails.service import GuardrailService
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
        documents: DocumentService,
        figure_checks: FigureCheckService,
        guardrails: GuardrailService,
    ) -> None:
        self.conversations = conversations
        self.messages = messages
        self.tool_calls = tool_calls
        self.documents = documents
        self.figure_checks = figure_checks
        self.guardrails = guardrails

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

    async def create_message(
        self, conversation_id: UUID, data: RequestMessageCreate, owner_id: UUID
    ) -> Message:
        """Store the user's message and return the stored reply, which may have used tools."""
        history, documents = await self._add_user_message(
            conversation_id=conversation_id, data=data, owner_id=owner_id
        )
        try:
            guardrail = await self.guardrails.check_message(text=data.content)
            if guardrail.decline is not None:
                content, provenance = guardrail.decline, guardrail.provenance
            else:
                messages = chat_prompt(history=history, page=data.page, documents=documents)
                answer, answer_provenance = await self.tool_calls.create_answer(
                    conversation_id=conversation_id,
                    message_id=history[-1].id,
                    messages=messages,
                )
                checked = await self._check_figures(
                    conversation_id=conversation_id,
                    content=answer,
                    provenance=answer_provenance,
                    history=history,
                    documents=documents,
                )
                content, provenance = _guarded(answer=(answer, checked), guardrail=guardrail)
        except Exception:
            await self.messages.delete(entity_id=history[-1].id)
            raise
        return await self._store_reply(
            conversation_id=conversation_id, content=content, provenance=provenance
        )

    async def stream_message(
        self, conversation_id: UUID, data: RequestMessageCreate, owner_id: UUID
    ) -> AsyncIterator[StreamEvent[Message]]:
        """Like `create_message`, but yields the turn's events, then the stored reply."""
        history, documents = await self._add_user_message(
            conversation_id=conversation_id, data=data, owner_id=owner_id
        )
        is_stored = False
        try:
            guardrail = await self.guardrails.check_message(text=data.content)
            if guardrail.decline is not None:
                yield TokenEvent(text=guardrail.decline)
                content, provenance = guardrail.decline, guardrail.provenance
            else:
                events = self.tool_calls.stream_answer(
                    conversation_id=conversation_id,
                    message_id=history[-1].id,
                    messages=chat_prompt(history=history, page=data.page, documents=documents),
                )
                async for event in events:
                    if not isinstance(event, DoneEvent):
                        yield event
                        continue
                    answer, answer_provenance = event.result
                    checked = await self._check_figures(
                        conversation_id=conversation_id,
                        content=answer,
                        provenance=answer_provenance,
                        history=history,
                        documents=documents,
                    )
                    content, provenance = _guarded(answer=(answer, checked), guardrail=guardrail)
                pointer = _pointer_text(guardrail=guardrail)
                if pointer != "":
                    yield TokenEvent(text=pointer)
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
        self, conversation_id: UUID, data: RequestMessageCreate, owner_id: UUID
    ) -> tuple[list[Message], list[Document]]:
        """Store the message; returns the recent history ending with it, and its documents."""
        # Read first: the write's commit then leaves no transaction open across the LLM call.
        history = await self.messages.list_recent(
            conversation_id=conversation_id, limit=HISTORY_LIMIT - 1
        )
        documents = await self.documents.get_documents(
            document_ids=data.document_ids, owner_id=owner_id
        )
        await self._check_quotes(conversation_id=conversation_id, data=data)
        message = await self.messages.create(
            conversation_id=conversation_id,
            role="user",
            content=data.content,
            quotes=[quote.model_dump(mode="json") for quote in data.quotes],
            documents=[
                MessageDocument(id=document.id, name=document.name).model_dump(mode="json")
                for document in documents
            ],
        )
        return [*history, message], documents

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

    async def _check_figures(
        self,
        conversation_id: UUID,
        content: str,
        provenance: Provenance,
        history: list[Message],
        documents: list[Document],
    ) -> Provenance:
        # Earlier turns count too, so a follow-up may repeat a figure it was shown before.
        calls = await self.tool_calls.list_tool_calls(conversation_id=conversation_id)
        sources = [
            json.dumps(call.result, ensure_ascii=False) for call in calls if call.result is not None
        ]
        sources += [document.markdown for document in documents]
        sources += [message.content for message in history if message.role == "user"]
        check = self.figure_checks.check_figures(answer=content, sources=sources)
        if check is None:
            return provenance
        return provenance.model_copy(update={"checks": [*provenance.checks, check]})

    async def _store_reply(
        self, conversation_id: UUID, content: str, provenance: Provenance
    ) -> Message:
        return await self.messages.create(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            provenance=provenance.model_dump(),
        )


def _pointer_text(guardrail: Guardrail) -> str:
    """The server's pointer as it follows the answer, or nothing."""
    return "" if guardrail.pointer is None else f"\n\n{guardrail.pointer}"


def _guarded(answer: tuple[str, Provenance], guardrail: Guardrail) -> tuple[str, Provenance]:
    """The answer followed by the server's pointer, with the guardrail check in its provenance."""
    content, provenance = answer
    checks = [*provenance.checks, *guardrail.provenance.checks]
    return content + _pointer_text(guardrail=guardrail), provenance.model_copy(
        update={"checks": checks}
    )
