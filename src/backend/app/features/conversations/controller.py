from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.auth import CurrentUserDep, require_user
from app.core.streaming import sse_response
from app.features.conversations.dependencies import ConversationServiceDep, OwnedConversationDep
from app.features.conversations.schemas import (
    Conversation,
    Message,
    RequestConversationCreate,
    RequestConversationUpdate,
    RequestMessageCreate,
    ResponseConversation,
    ResponseMessage,
)
from app.features.tool_calls.dependencies import ToolCallServiceDep
from app.features.tool_calls.schemas import ResponseToolCall, ToolCall

router = APIRouter(
    prefix="/conversations", tags=["conversations"], dependencies=[Depends(require_user)]
)


def _conversation_response(conversation: Conversation) -> ResponseConversation:
    return ResponseConversation.model_validate(conversation, from_attributes=True)


def _message_response(message: Message) -> ResponseMessage:
    return ResponseMessage.model_validate(message, from_attributes=True)


def _tool_call_response(tool_call: ToolCall) -> ResponseToolCall:
    return ResponseToolCall.model_validate(tool_call, from_attributes=True)


@router.post("", response_model=ResponseConversation, status_code=201)
async def create_conversation(
    body: RequestConversationCreate, user: CurrentUserDep, service: ConversationServiceDep
) -> ResponseConversation:
    """Start a new conversation."""
    conversation = await service.create_conversation(data=body, owner_id=user.id)
    return _conversation_response(conversation=conversation)


@router.get("", response_model=list[ResponseConversation])
async def list_conversations(
    user: CurrentUserDep, service: ConversationServiceDep, sort: str | None = None
) -> list[ResponseConversation]:
    """List your conversations, newest first by default."""
    conversations = await service.list_conversations(owner_id=user.id, sort=sort)
    return [_conversation_response(conversation=conversation) for conversation in conversations]


@router.get("/{conversation_id}", response_model=ResponseConversation)
async def get_conversation(conversation: OwnedConversationDep) -> ResponseConversation:
    """Get one conversation."""
    return _conversation_response(conversation=conversation)


@router.patch("/{conversation_id}", response_model=ResponseConversation)
async def update_conversation(
    body: RequestConversationUpdate,
    conversation: OwnedConversationDep,
    service: ConversationServiceDep,
) -> ResponseConversation:
    """Rename a conversation."""
    updated = await service.update_conversation(conversation_id=conversation.id, data=body)
    return _conversation_response(conversation=updated)


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation: OwnedConversationDep, service: ConversationServiceDep
) -> None:
    """Delete a conversation and its messages."""
    await service.delete_conversation(conversation_id=conversation.id)


@router.get("/{conversation_id}/messages", response_model=list[ResponseMessage])
async def list_messages(
    conversation: OwnedConversationDep, service: ConversationServiceDep, sort: str | None = None
) -> list[ResponseMessage]:
    """List a conversation's messages, oldest first by default."""
    messages = await service.list_messages(conversation_id=conversation.id, sort=sort)
    return [_message_response(message=message) for message in messages]


@router.post("/{conversation_id}/messages", response_model=ResponseMessage, status_code=201)
async def create_message(
    body: RequestMessageCreate,
    conversation: OwnedConversationDep,
    service: ConversationServiceDep,
    stream: bool = False,
) -> ResponseMessage | StreamingResponse:
    """Send a message and get the reply, which may use tools; `?stream=true` streams it as SSE."""
    if stream:
        events = service.stream_message(conversation_id=conversation.id, data=body)
        return sse_response(events=events, to_response=_message_response)
    message = await service.create_message(conversation_id=conversation.id, data=body)
    return _message_response(message=message)


@router.get("/{conversation_id}/tool-calls", response_model=list[ResponseToolCall])
async def list_tool_calls(
    conversation: OwnedConversationDep, service: ToolCallServiceDep
) -> list[ResponseToolCall]:
    """List the tool calls made in a conversation, oldest first."""
    tool_calls = await service.list_tool_calls(conversation_id=conversation.id)
    return [_tool_call_response(tool_call=tool_call) for tool_call in tool_calls]
