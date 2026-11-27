from typing import Annotated
from uuid import UUID

from fastapi import Depends

from app.core.auth import CurrentUserDep
from app.core.db import SessionDep
from app.features.conversations.repository import ConversationRepository, MessageRepository
from app.features.conversations.schemas import Conversation
from app.features.conversations.service import ConversationService
from app.features.documents.dependencies import DocumentServiceDep
from app.features.figure_checks.dependencies import FigureCheckServiceDep
from app.features.tool_calls.dependencies import ToolCallServiceDep


def get_conversation_repo(session: SessionDep) -> ConversationRepository:
    return ConversationRepository(session=session)


def get_message_repo(session: SessionDep) -> MessageRepository:
    return MessageRepository(session=session)


def get_conversation_service(
    conversations: Annotated[ConversationRepository, Depends(get_conversation_repo)],
    messages: Annotated[MessageRepository, Depends(get_message_repo)],
    tool_calls: ToolCallServiceDep,
    documents: DocumentServiceDep,
    figure_checks: FigureCheckServiceDep,
) -> ConversationService:
    return ConversationService(
        conversations=conversations,
        messages=messages,
        tool_calls=tool_calls,
        documents=documents,
        figure_checks=figure_checks,
    )


ConversationServiceDep = Annotated[ConversationService, Depends(get_conversation_service)]


async def get_owned_conversation(
    conversation_id: UUID, user: CurrentUserDep, service: ConversationServiceDep
) -> Conversation:
    return await service.get_conversation(conversation_id=conversation_id, owner_id=user.id)


OwnedConversationDep = Annotated[Conversation, Depends(get_owned_conversation)]
