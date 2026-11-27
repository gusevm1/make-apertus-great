from uuid import UUID

from sqlalchemy import select

from app.core.repository import BaseRepository
from app.features.documents.models import DocumentORM
from app.features.documents.schemas import Document


class DocumentRepository(BaseRepository[DocumentORM, Document]):
    orm_model = DocumentORM
    schema = Document

    async def list_owned(self, document_ids: list[UUID], owner_id: UUID) -> list[Document]:
        stmt = select(DocumentORM).where(
            DocumentORM.id.in_(document_ids), DocumentORM.owner_id == owner_id
        )
        rows = await self.session.scalars(stmt)
        return [self._to_schema(row=row) for row in rows]

    async def list_by_owner(self, owner_id: UUID) -> list[Document]:
        documents = await self.list(owner_id=owner_id)
        # Ends the read, so no transaction stays open during the model call that follows.
        await self.session.commit()
        return documents
