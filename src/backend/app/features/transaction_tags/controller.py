from fastapi import APIRouter, Depends

from app.core.auth import CurrentUserDep, require_user
from app.features.transaction_tags.dependencies import SeverityServiceDep, TransactionTagServiceDep
from app.features.transaction_tags.schemas import (
    Categorisation,
    RatedTransactionTag,
    RequestSeverityUpdate,
    ResponseCategorisation,
    ResponseSeveritySetting,
    ResponseTransactionTag,
    SeveritySetting,
)

router = APIRouter(tags=["transaction-tags"], dependencies=[Depends(require_user)])


def _tag_response(tag: RatedTransactionTag) -> ResponseTransactionTag:
    return ResponseTransactionTag.model_validate(tag, from_attributes=True)


def _setting_response(setting: SeveritySetting) -> ResponseSeveritySetting:
    return ResponseSeveritySetting.model_validate(setting, from_attributes=True)


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
    user: CurrentUserDep, service: SeverityServiceDep, sort: str | None = None
) -> list[ResponseTransactionTag]:
    """List your categorised rows with their severity, newest first by default."""
    tags = await service.list_rated_tags(owner_id=user.id, token=user.token, sort=sort)
    return [_tag_response(tag=tag) for tag in tags]


@router.post("/severity-proposals", response_model=list[ResponseSeveritySetting], status_code=201)
async def create_severity_proposal(
    user: CurrentUserDep, service: SeverityServiceDep
) -> list[ResponseSeveritySetting]:
    """Have Apertus rate the categories you have no severity for yet."""
    settings = await service.create_proposal(owner_id=user.id, token=user.token)
    return [_setting_response(setting=setting) for setting in settings]


@router.get("/severity-settings", response_model=list[ResponseSeveritySetting])
async def list_severity_settings(
    user: CurrentUserDep, service: SeverityServiceDep
) -> list[ResponseSeveritySetting]:
    """List your severities for categories, payees and single bookings."""
    settings = await service.list_settings(owner_id=user.id)
    return [_setting_response(setting=setting) for setting in settings]


@router.patch("/severity-settings", response_model=ResponseSeveritySetting)
async def update_severity_setting(
    data: RequestSeverityUpdate, user: CurrentUserDep, service: SeverityServiceDep
) -> ResponseSeveritySetting:
    """Set your own severity for a category, a payee or a booking."""
    setting = await service.update_setting(owner_id=user.id, token=user.token, data=data)
    return _setting_response(setting=setting)
