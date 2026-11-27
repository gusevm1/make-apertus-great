from typing import Annotated

from fastapi import Depends

from app.clients.apertus import ApertusClientDep
from app.core.db import SessionDep
from app.features.ledger.dependencies import LedgerServiceDep
from app.features.transaction_tags.repository import TransactionTagRepository
from app.features.transaction_tags.service import TransactionTagService


def get_transaction_tag_repo(session: SessionDep) -> TransactionTagRepository:
    return TransactionTagRepository(session=session)


def get_transaction_tag_service(
    tags: Annotated[TransactionTagRepository, Depends(get_transaction_tag_repo)],
    ledger: LedgerServiceDep,
    apertus: ApertusClientDep,
) -> TransactionTagService:
    return TransactionTagService(tags=tags, ledger=ledger, apertus=apertus)


TransactionTagServiceDep = Annotated[TransactionTagService, Depends(get_transaction_tag_service)]
