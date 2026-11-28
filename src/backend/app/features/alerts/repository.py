from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.core.repository import BaseRepository
from app.features.alerts.models import AlertDismissalORM, AlertSettingORM
from app.features.alerts.schemas import AlertDismissal, AlertKind, AlertSetting


class AlertDismissalRepository(BaseRepository[AlertDismissalORM, AlertDismissal]):
    orm_model = AlertDismissalORM
    schema = AlertDismissal

    async def get_owned(self, dismissal_id: UUID, owner_id: UUID) -> AlertDismissal | None:
        stmt = select(AlertDismissalORM).filter_by(id=dismissal_id, owner_id=owner_id)
        row = await self.session.scalar(stmt)
        return self._to_schema(row=row) if row is not None else None

    # A second Done on the same flag returns the first one instead of failing.
    async def add(self, owner_id: UUID, key: str) -> AlertDismissal:
        stmt = (
            insert(AlertDismissalORM)
            .values(owner_id=owner_id, key=key)
            .on_conflict_do_nothing(index_elements=["owner_id", "key"])
        )
        await self.session.execute(stmt)
        await self.session.commit()
        row = await self.session.scalar(
            select(AlertDismissalORM).filter_by(owner_id=owner_id, key=key)
        )
        return self._to_schema(row=row)


class AlertSettingRepository(BaseRepository[AlertSettingORM, AlertSetting]):
    orm_model = AlertSettingORM
    schema = AlertSetting

    async def upsert(self, owner_id: UUID, kind: AlertKind, enabled: bool) -> AlertSetting:
        stmt = (
            insert(AlertSettingORM)
            .values(owner_id=owner_id, kind=kind, enabled=enabled)
            .on_conflict_do_update(index_elements=["owner_id", "kind"], set_={"enabled": enabled})
            .returning(AlertSettingORM)
        )
        row = await self.session.scalar(stmt)
        await self.session.commit()
        return self._to_schema(row=row)

    async def delete_kind(self, owner_id: UUID, kind: AlertKind) -> None:
        await self.session.execute(delete(AlertSettingORM).filter_by(owner_id=owner_id, kind=kind))
        await self.session.commit()
