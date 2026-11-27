from typing import Annotated

from fastapi import Depends

from app.features.context_entries.dependencies import ContextEntryServiceDep
from app.features.customer_contexts.service import CustomerContextService
from app.features.documents.dependencies import DocumentServiceDep


def get_customer_context_service(
    documents: DocumentServiceDep, context_entries: ContextEntryServiceDep
) -> CustomerContextService:
    return CustomerContextService(documents=documents, context_entries=context_entries)


CustomerContextServiceDep = Annotated[CustomerContextService, Depends(get_customer_context_service)]
