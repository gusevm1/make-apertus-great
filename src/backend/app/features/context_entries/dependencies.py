from typing import Annotated
from uuid import UUID

from fastapi import Depends

from app.core.auth import CurrentUserDep
from app.core.db import SessionDep
from app.features.context_entries.repository import ContextEntryRepository
from app.features.context_entries.schemas import ContextEntry
from app.features.context_entries.service import ContextEntryService


def get_context_entry_service(session: SessionDep) -> ContextEntryService:
    return ContextEntryService(entries=ContextEntryRepository(session=session))


ContextEntryServiceDep = Annotated[ContextEntryService, Depends(get_context_entry_service)]


async def get_owned_context_entry(
    entry_id: UUID, user: CurrentUserDep, service: ContextEntryServiceDep
) -> ContextEntry:
    return await service.get_entry(entry_id=entry_id, owner_id=user.id)


OwnedContextEntryDep = Annotated[ContextEntry, Depends(get_owned_context_entry)]
