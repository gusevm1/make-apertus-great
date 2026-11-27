from uuid import UUID

from sqlalchemy import select

from app.core.repository import BaseRepository
from app.features.conversations.models import ConversationORM, MessageORM
from app.features.conversations.schemas import Conversation, Message


class ConversationRepository(BaseRepository[ConversationORM, Conversation]):
    orm_model = ConversationORM
    schema = Conversation

    async def get_owned(self, conversation_id: UUID, owner_id: UUID) -> Conversation | None:
        stmt = select(ConversationORM).filter_by(id=conversation_id, owner_id=owner_id)
        row = await self.session.scalar(stmt)
        return self._to_schema(row=row) if row is not None else None


class MessageRepository(BaseRepository[MessageORM, Message]):
    orm_model = MessageORM
    schema = Message
    default_sort = "created_at"

    async def list_recent(self, conversation_id: UUID, limit: int) -> list[Message]:
        stmt = (
            select(MessageORM)
            .filter_by(conversation_id=conversation_id)
            .order_by(MessageORM.created_at.desc())
            .limit(limit)
        )
        rows = await self.session.scalars(stmt)
        return [self._to_schema(row=row) for row in rows][::-1]

    async def list_contents(
        self, conversation_id: UUID, message_ids: list[UUID]
    ) -> dict[UUID, str]:
        stmt = select(MessageORM.id, MessageORM.content).where(
            MessageORM.conversation_id == conversation_id, MessageORM.id.in_(message_ids)
        )
        rows = await self.session.execute(stmt)
        return {row.id: row.content for row in rows}
