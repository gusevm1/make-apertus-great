from uuid import UUID

from app.core.errors import ConflictError, NotFoundError
from app.features.context_entries.repository import ContextEntryRepository
from app.features.context_entries.schemas import (
    ACTIVE_ENTRIES_MAX,
    ContextEntry,
    RequestContextEntryCreate,
    RequestContextEntryUpdate,
    Status,
)

COPIED_FIELDS = ("owner_id", "kind", "text", "amount_chf", "target_date", "source", "source_id")


class ContextEntryService:
    def __init__(self, entries: ContextEntryRepository) -> None:
        self.entries = entries

    async def create_entry(self, data: RequestContextEntryCreate, owner_id: UUID) -> ContextEntry:
        """Store an active entry the customer wrote."""
        # ponytail: count then insert, two parallel requests can pass 50; a lock if it matters
        if await self.entries.count_active(owner_id=owner_id) >= ACTIVE_ENTRIES_MAX:
            raise ConflictError(
                f"You already have {ACTIVE_ENTRIES_MAX} entries. Delete one to add another."
            )
        return await self.entries.create(
            data=data, owner_id=owner_id, status="active", source="customer"
        )

    async def list_entries(
        self, owner_id: UUID, status: Status = "active", sort: str | None = None
    ) -> list[ContextEntry]:
        """List the customer's entries with one status."""
        return await self.entries.list(sort=sort, owner_id=owner_id, status=status)

    async def get_entry(self, entry_id: UUID, owner_id: UUID) -> ContextEntry:
        """Return the customer's entry; someone else's counts as not found."""
        entry = await self.entries.get_owned(entry_id=entry_id, owner_id=owner_id)
        if entry is None:
            raise NotFoundError("Context entry not found")
        return entry

    async def update_entry(
        self, entry: ContextEntry, data: RequestContextEntryUpdate
    ) -> ContextEntry:
        """Store the changed entry as a new one and mark the old one replaced."""
        if entry.status != "active":
            raise ConflictError(f"Only an active entry can be changed, this one is {entry.status}")
        fields = {name: getattr(entry, name) for name in COPIED_FIELDS}
        fields |= data.model_dump(exclude_unset=True)
        new = await self.entries.replace(entry_id=entry.id, fields={**fields, "status": "active"})
        if new is None:
            raise ConflictError("This entry was changed meanwhile, reload it")
        return new

    async def delete_entry(self, entry_id: UUID) -> None:
        """Delete the entry and, through the FK cascade, its earlier versions."""
        if not await self.entries.delete(entity_id=entry_id):
            raise NotFoundError("Context entry not found")
