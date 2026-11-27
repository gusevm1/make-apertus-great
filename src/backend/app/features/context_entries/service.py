from uuid import UUID

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.features.context_entries.repository import ContextEntryRepository
from app.features.context_entries.schemas import (
    ACTIVE_ENTRIES_MAX,
    LIST_MAX_CHARS,
    ContextEntry,
    ContextEntryList,
    ContextEntrySummary,
    RequestContextEntryCreate,
    RequestContextEntryUpdate,
    Status,
)

DUPLICATE_MESSAGES = {
    "active": "The customer has this entry already. Do not propose it again.",
    "proposed": "This proposal waits for the customer already. Do not propose it again.",
    "dismissed": "The customer dismissed this proposal before. Do not propose it again.",
}
COPIED_FIELDS = ("owner_id", "kind", "text", "amount_chf", "target_date", "source", "source_id")


class ContextEntryService:
    def __init__(self, entries: ContextEntryRepository) -> None:
        self.entries = entries

    async def create_entry(self, data: RequestContextEntryCreate, owner_id: UUID) -> ContextEntry:
        """Store an active entry the customer wrote."""
        await self._check_room(owner_id=owner_id)
        return await self.entries.create(
            data=data, owner_id=owner_id, status="active", source="customer"
        )

    async def propose_entry(
        self,
        data: RequestContextEntryCreate,
        replaces: str | None,
        owner_id: UUID,
        tool_call_id: UUID,
    ) -> ContextEntry:
        """Store the chat's proposal, which waits for the customer to confirm or dismiss it."""
        entries = await self.entries.list(owner_id=owner_id)
        same = next(
            (
                entry
                for entry in entries
                if entry.status != "replaced" and _same(entry=entry, data=data)
            ),
            None,
        )
        if same is not None:
            raise ConflictError(DUPLICATE_MESSAGES[same.status])
        replaced = None
        if replaces is not None:
            replaced = _find_active(entries=entries, words=replaces)
        return await self.entries.create(
            data=data,
            owner_id=owner_id,
            status="proposed",
            source="chat",
            source_id=tool_call_id,
            replaces_id=None if replaced is None else replaced.id,
        )

    async def list_entries(
        self, owner_id: UUID, status: Status = "active", sort: str | None = None
    ) -> list[ContextEntry]:
        """List the customer's entries with one status."""
        return await self.entries.list(sort=sort, owner_id=owner_id, status=status)

    async def list_summaries(self, owner_id: UUID, text: str | None) -> ContextEntryList:
        """The newest active entries that fit, at least one, holding a word of `text` if given."""
        words = [] if text is None else text.split()
        entries = await self.entries.list_active(owner_id=owner_id, words=words)
        summaries: list[ContextEntrySummary] = []
        used = 0
        for entry in entries:
            summary = ContextEntrySummary.model_validate(entry, from_attributes=True)
            used += len(summary.model_dump_json())
            if used > LIST_MAX_CHARS and summaries:
                break
            summaries.append(summary)
        return ContextEntryList(entries=summaries, left_out=len(entries) - len(summaries))

    async def get_entry(self, entry_id: UUID, owner_id: UUID) -> ContextEntry:
        """Return the customer's entry; someone else's counts as not found."""
        entry = await self.entries.get_owned(entry_id=entry_id, owner_id=owner_id)
        if entry is None:
            raise NotFoundError("Context entry not found")
        return entry

    async def update_entry(
        self, entry: ContextEntry, data: RequestContextEntryUpdate
    ) -> ContextEntry:
        """Store a changed entry as a new one, or confirm or dismiss a proposal."""
        if entry.status == "proposed":
            return await self._answer_proposal(entry=entry, data=data)
        if entry.status != "active":
            raise ConflictError(f"Only an active entry can be changed, this one is {entry.status}")
        if data.status is not None:
            raise BadRequestError("Only a proposed entry is confirmed or dismissed")
        fields = {name: getattr(entry, name) for name in COPIED_FIELDS}
        fields |= data.model_dump(exclude_unset=True)
        new = await self.entries.replace(entry_id=entry.id, fields={**fields, "status": "active"})
        if new is None:
            raise ConflictError("This entry was changed meanwhile, reload it")
        return new

    async def _answer_proposal(
        self, entry: ContextEntry, data: RequestContextEntryUpdate
    ) -> ContextEntry:
        if data.status is None:
            raise BadRequestError(
                "Send status active to confirm the proposal or dismissed to drop it"
            )
        if data.status == "dismissed":
            fields, replaces_id = {"status": "dismissed"}, None
        else:
            if entry.replaces_id is None:
                await self._check_room(owner_id=entry.owner_id)
            fields, replaces_id = data.model_dump(exclude_unset=True), entry.replaces_id
        answered = await self.entries.answer_proposal(
            entry_id=entry.id, fields=fields, replaces_id=replaces_id
        )
        if answered is None:
            raise ConflictError(
                "This entry or the one it replaces was changed meanwhile, reload it"
            )
        return answered

    async def _check_room(self, owner_id: UUID) -> None:
        # ponytail: count then insert, two parallel requests can pass 50; a lock if it matters
        if await self.entries.count_active(owner_id=owner_id) >= ACTIVE_ENTRIES_MAX:
            raise ConflictError(
                f"You already have {ACTIVE_ENTRIES_MAX} entries. Delete one to add another."
            )

    async def delete_entry(self, entry_id: UUID) -> None:
        """Delete the entry and, through the FK cascade, its earlier versions."""
        if not await self.entries.delete(entity_id=entry_id):
            raise NotFoundError("Context entry not found")


def _normal(text: str) -> str:
    return " ".join(text.casefold().split())


def _same(entry: ContextEntry, data: RequestContextEntryCreate) -> bool:
    return (entry.kind, _normal(text=entry.text), entry.amount_chf, entry.target_date) == (
        data.kind,
        _normal(text=data.text),
        data.amount_chf,
        data.target_date,
    )


def _find_active(entries: list[ContextEntry], words: str) -> ContextEntry:
    active = [entry for entry in entries if entry.status == "active"]
    found = [entry for entry in active if _normal(text=words) in _normal(text=entry.text)]
    if len(found) == 1:
        return found[0]
    listed = "\n".join(f"- {entry.kind}: {entry.text}" for entry in active) or "- none"
    raise NotFoundError(
        f"No single active entry has the words '{words}'. "
        f"Send the words of one of these, or leave replaces out:\n{listed}"
    )
