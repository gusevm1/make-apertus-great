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
