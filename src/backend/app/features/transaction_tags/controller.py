from fastapi import APIRouter, Depends

from app.core.auth import CurrentUserDep, require_user
from app.features.transaction_tags.dependencies import TransactionTagServiceDep
from app.features.transaction_tags.schemas import (
    Categorisation,
    ResponseCategorisation,
    ResponseTransactionTag,
    TransactionTag,
)

router = APIRouter(tags=["transaction-tags"], dependencies=[Depends(require_user)])


def _tag_response(tag: TransactionTag) -> ResponseTransactionTag:
    return ResponseTransactionTag.model_validate(tag, from_attributes=True)


def _categorisation_response(categorisation: Categorisation) -> ResponseCategorisation:
    return ResponseCategorisation.model_validate(categorisation, from_attributes=True)


@router.post("/categorisations", response_model=ResponseCategorisation, status_code=201)
async def create_categorisation(
    user: CurrentUserDep, service: TransactionTagServiceDep
) -> ResponseCategorisation:
    """Categorise the spending rows that have no category yet."""
    categorisation = await service.create_categorisation(owner_id=user.id, token=user.token)
    return _categorisation_response(categorisation=categorisation)


@router.get("/transaction-tags", response_model=list[ResponseTransactionTag])
async def list_transaction_tags(
    user: CurrentUserDep, service: TransactionTagServiceDep, sort: str | None = None
) -> list[ResponseTransactionTag]:
    """List your categorised rows, newest first by default."""
    tags = await service.list_tags(owner_id=user.id, sort=sort)
    return [_tag_response(tag=tag) for tag in tags]
