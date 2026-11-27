from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.core.repository import BaseRepository
from app.features.transaction_tags.models import SeveritySettingORM, TransactionTagORM
from app.features.transaction_tags.schemas import SeveritySetting, TransactionTag


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

    async def list_categories(self, owner_id: UUID) -> dict[tuple[str, str], str]:
        """The category of every tagged row, by (row_source, row_id)."""
        stmt = select(
            TransactionTagORM.row_source, TransactionTagORM.row_id, TransactionTagORM.category
        ).where(TransactionTagORM.owner_id == owner_id)
        rows = await self.session.execute(stmt)
        categories = {(row.row_source, row.row_id): row.category for row in rows}
        await self.session.commit()
        return categories

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


class SeveritySettingRepository(BaseRepository[SeveritySettingORM, SeveritySetting]):
    orm_model = SeveritySettingORM
    schema = SeveritySetting

    async def list_for_owner(self, owner_id: UUID) -> list[SeveritySetting]:
        settings = await self.list(owner_id=owner_id)
        # Ends the read's transaction, so none stays open while Apertus works.
        await self.session.commit()
        return settings

    async def create_missing(self, values: list[dict[str, object]]) -> None:
        """Store settings, keeping the ones that exist already."""
        if not values:
            return
        stmt = (
            insert(SeveritySettingORM)
            .values(values)
            .on_conflict_do_nothing(index_elements=["owner_id", "scope", "key"])
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def upsert(self, values: dict[str, object]) -> SeveritySetting:
        stmt = (
            insert(SeveritySettingORM)
            .values(values)
            .on_conflict_do_update(
                index_elements=["owner_id", "scope", "key"],
                set_={
                    "severity": values["severity"],
                    "set_by": values["set_by"],
                    "model": values["model"],
                    "confirmed": values["confirmed"],
                    "reason": values["reason"],
                    "updated_at": func.now(),
                },
            )
            .returning(SeveritySettingORM)
        )
        row = (await self.session.scalars(stmt)).one()
        setting = self._to_schema(row=row)
        await self.session.commit()
        return setting
