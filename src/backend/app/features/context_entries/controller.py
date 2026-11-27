from fastapi import APIRouter, Depends

from app.core.auth import CurrentUserDep, require_user
from app.features.context_entries.dependencies import (
    ContextEntryServiceDep,
    OwnedContextEntryDep,
)
from app.features.context_entries.schemas import (
    ContextEntry,
    RequestContextEntryCreate,
    RequestContextEntryUpdate,
    ResponseContextEntry,
    Status,
)

router = APIRouter(
    prefix="/context-entries", tags=["context-entries"], dependencies=[Depends(require_user)]
)


def _entry_response(entry: ContextEntry) -> ResponseContextEntry:
    return ResponseContextEntry.model_validate(entry, from_attributes=True)


@router.post("", response_model=ResponseContextEntry, status_code=201)
async def create_context_entry(
    body: RequestContextEntryCreate, user: CurrentUserDep, service: ContextEntryServiceDep
) -> ResponseContextEntry:
    """Store a goal, fact or preference the customer wrote."""
    entry = await service.create_entry(data=body, owner_id=user.id)
    return _entry_response(entry=entry)


@router.get("", response_model=list[ResponseContextEntry])
async def list_context_entries(
    user: CurrentUserDep,
    service: ContextEntryServiceDep,
    status: Status = "active",
    sort: str | None = None,
) -> list[ResponseContextEntry]:
    """List your active entries, or those with `?status=`, newest first by default."""
    entries = await service.list_entries(owner_id=user.id, status=status, sort=sort)
    return [_entry_response(entry=entry) for entry in entries]


@router.patch("/{entry_id}", response_model=ResponseContextEntry)
async def update_context_entry(
    body: RequestContextEntryUpdate, entry: OwnedContextEntryDep, service: ContextEntryServiceDep
) -> ResponseContextEntry:
    """Change an active entry into a new one (the old one is kept), or answer a proposal."""
    updated = await service.update_entry(entry=entry, data=body)
    return _entry_response(entry=updated)


@router.delete("/{entry_id}", status_code=204)
async def delete_context_entry(
    entry: OwnedContextEntryDep, service: ContextEntryServiceDep
) -> None:
    """Delete an entry and every earlier version of it."""
    await service.delete_entry(entry_id=entry.id)
