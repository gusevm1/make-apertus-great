from typing import Any
from uuid import UUID

from app.features.context_entries.service import ContextEntryService
from app.features.customer_contexts.prompts import customer_block
from app.features.documents.service import DocumentService

DOCUMENTS_MAX = 20
ENTRIES_MAX = 50


class CustomerContextService:
    def __init__(self, documents: DocumentService, context_entries: ContextEntryService) -> None:
        self.documents = documents
        self.context_entries = context_entries

    async def get_customer_block(self, owner_id: UUID, profile: dict[str, Any]) -> str:
        """Who the customer is, for a chat turn: profile, newest documents and active entries."""
        # ponytail: loads every document with its text to keep 20; a list without markdown if slow
        documents = await self.documents.list_documents(owner_id=owner_id)
        entries = await self.context_entries.list_entries(owner_id=owner_id)
        return customer_block(
            profile=profile, documents=documents[:DOCUMENTS_MAX], entries=entries[:ENTRIES_MAX]
        )
