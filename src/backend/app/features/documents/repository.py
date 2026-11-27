from uuid import UUID

from sqlalchemy import case, or_, select

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

    # With words, only the documents holding one in name, title, issuer or summary, those holding
    # the most first; then newest first.
    async def list_matching(self, owner_id: UUID, words: list[str]) -> list[Document]:
        stmt = select(DocumentORM).where(DocumentORM.owner_id == owner_id)
        if words:
            columns = (DocumentORM.name, DocumentORM.title, DocumentORM.issuer, DocumentORM.summary)
            matches = [
                or_(*(column.icontains(word, autoescape=True) for column in columns))
                for word in words
            ]
            first, *rest = [case((match, 1), else_=0) for match in matches]
            hits = sum(rest, first)
            stmt = stmt.where(or_(*matches)).order_by(hits.desc())
        rows = await self.session.scalars(stmt.order_by(DocumentORM.created_at.desc()))
        return [self._to_schema(row=row) for row in rows]
