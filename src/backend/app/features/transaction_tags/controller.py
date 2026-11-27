from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.auth import CurrentUserDep, require_user
from app.features.transaction_tags.dependencies import (
    OwnedPersonalTagDep,
    PersonalTagServiceDep,
    SeverityServiceDep,
    TransactionTagServiceDep,
)
from app.features.transaction_tags.schemas import (
    AssignedRow,
    Categorisation,
    PersonalTagSummary,
    RatedTransactionTag,
    RequestPersonalTagAssignmentCreate,
    RequestPersonalTagCreate,
    RequestPersonalTagUpdate,
    RequestSeverityUpdate,
    ResponseCategorisation,
    ResponsePersonalTag,
    ResponsePersonalTagAssignment,
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


def _personal_tag_response(tag: PersonalTagSummary) -> ResponsePersonalTag:
    return ResponsePersonalTag.model_validate(tag, from_attributes=True)


def _assignment_response(row: AssignedRow) -> ResponsePersonalTagAssignment:
    return ResponsePersonalTagAssignment.model_validate(row, from_attributes=True)


@router.get("/personal-tags", response_model=list[ResponsePersonalTag])
async def list_personal_tags(
    user: CurrentUserDep, service: PersonalTagServiceDep
) -> list[ResponsePersonalTag]:
    """List your personal tags with what their spending and own transfers add up to."""
    tags = await service.list_tags(owner_id=user.id, token=user.token)
    return [_personal_tag_response(tag=tag) for tag in tags]


@router.post("/personal-tags", response_model=ResponsePersonalTag, status_code=201)
async def create_personal_tag(
    data: RequestPersonalTagCreate, user: CurrentUserDep, service: PersonalTagServiceDep
) -> ResponsePersonalTag:
    """Create a personal tag of your own."""
    tag = await service.create_tag(owner_id=user.id, token=user.token, data=data)
    return _personal_tag_response(tag=tag)


@router.patch("/personal-tags/{tag_id}", response_model=ResponsePersonalTag)
async def update_personal_tag(
    data: RequestPersonalTagUpdate,
    tag: OwnedPersonalTagDep,
    user: CurrentUserDep,
    service: PersonalTagServiceDep,
) -> ResponsePersonalTag:
    """Rename a personal tag or change its description."""
    updated = await service.update_tag(tag=tag, token=user.token, data=data)
    return _personal_tag_response(tag=updated)


@router.delete("/personal-tags/{tag_id}", status_code=204)
async def delete_personal_tag(tag: OwnedPersonalTagDep, service: PersonalTagServiceDep) -> None:
    """Delete a personal tag and its assignments."""
    await service.delete_tag(tag=tag)


@router.get(
    "/personal-tags/{tag_id}/assignments", response_model=list[ResponsePersonalTagAssignment]
)
async def list_personal_tag_assignments(
    tag: OwnedPersonalTagDep, user: CurrentUserDep, service: PersonalTagServiceDep
) -> list[ResponsePersonalTagAssignment]:
    """List the rows under a personal tag."""
    rows = await service.list_assigned_rows(tag=tag, token=user.token)
    return [_assignment_response(row=row) for row in rows]


@router.post(
    "/personal-tags/{tag_id}/assignments",
    response_model=ResponsePersonalTagAssignment,
    status_code=201,
)
async def create_personal_tag_assignment(
    data: RequestPersonalTagAssignmentCreate,
    tag: OwnedPersonalTagDep,
    user: CurrentUserDep,
    service: PersonalTagServiceDep,
) -> ResponsePersonalTagAssignment:
    """Put a spending or own-transfer row under a personal tag."""
    row = await service.create_assignment(tag=tag, token=user.token, data=data)
    return _assignment_response(row=row)


@router.delete("/personal-tags/{tag_id}/assignments/{assignment_id}", status_code=204)
async def delete_personal_tag_assignment(
    assignment_id: UUID, tag: OwnedPersonalTagDep, service: PersonalTagServiceDep
) -> None:
    """Take a row out from under a personal tag."""
    await service.delete_assignment(tag=tag, assignment_id=assignment_id)


@router.post("/personal-tag-inferences", response_model=list[ResponsePersonalTag], status_code=201)
async def create_personal_tag_inference(
    user: CurrentUserDep, service: PersonalTagServiceDep
) -> list[ResponsePersonalTag]:
    """Have Apertus infer your personal tags once and assign the rows no earlier run judged."""
    tags = await service.create_inference(owner_id=user.id, token=user.token)
    return [_personal_tag_response(tag=tag) for tag in tags]
