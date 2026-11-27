from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.repository import BaseRepository
from app.features.transaction_tags.models import TransactionTagORM
from app.features.transaction_tags.schemas import TransactionTag


class TransactionTagRepository(BaseRepository[TransactionTagORM, TransactionTag]):
    orm_model = TransactionTagORM
    schema = TransactionTag

    async def list_row_keys(self, owner_id: UUID) -> set[tuple[str, str]]:
        stmt = select(TransactionTagORM.row_source, TransactionTagORM.row_id).where(
            TransactionTagORM.owner_id == owner_id
        )
        rows = await self.session.execute(stmt)
        keys = {(row.row_source, row.row_id) for row in rows}
        # Ends the read's transaction, so none stays open while Apertus works.
        await self.session.commit()
        return keys

    async def create_many(self, values: list[dict[str, object]]) -> int:
        """Store tags, keeping rows that are tagged already; returns how many are new."""
        if not values:
            return 0
        stmt = (
            insert(TransactionTagORM)
            .values(values)
            .on_conflict_do_nothing(index_elements=["owner_id", "row_source", "row_id"])
            .returning(TransactionTagORM.id)
        )
        created = len((await self.session.scalars(stmt)).all())
        await self.session.commit()
        return created
