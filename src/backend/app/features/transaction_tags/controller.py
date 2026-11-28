from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.core.auth import CurrentUserDep, require_user
from app.features.transaction_tags.dependencies import (
    CategorisationRunServiceDep,
    OwnedCategorisationDep,
    OwnedPersonalTagDep,
    PersonalTagServiceDep,
    SeverityServiceDep,
    TransactionTagServiceDep,
)
from app.features.transaction_tags.schemas import (
    CATEGORY_NAME_MAX_LENGTH,
    AssignedRow,
    CategorisationRun,
    CategoryCorrectionResult,
    CategorySummary,
    CertaintyFilter,
    PersonalTagSummary,
    RatedTransactionTag,
    RequestCategorisationCreate,
    RequestCategoryCorrectionCreate,
    RequestPersonalTagAssignmentCreate,
    RequestPersonalTagCreate,
    RequestPersonalTagUpdate,
    RequestSeverityUpdate,
    RequestSpendingCategoryCreate,
    ResponseCategorisationRun,
    ResponseCategoryCorrection,
    ResponseCategorySummary,
    ResponsePersonalTag,
    ResponsePersonalTagAssignment,
    ResponseSeveritySetting,
    ResponseSpendingCategory,
    ResponseTransactionTag,
    SeveritySetting,
    SpendingCategory,
)

router = APIRouter(tags=["transaction-tags"], dependencies=[Depends(require_user)])


def _tag_response(tag: RatedTransactionTag) -> ResponseTransactionTag:
    return ResponseTransactionTag.model_validate(tag, from_attributes=True)


def _setting_response(setting: SeveritySetting) -> ResponseSeveritySetting:
    return ResponseSeveritySetting.model_validate(setting, from_attributes=True)


def _categorisation_response(run: CategorisationRun) -> ResponseCategorisationRun:
    return ResponseCategorisationRun.model_validate(run, from_attributes=True)


@router.post("/categorisations", response_model=ResponseCategorisationRun, status_code=202)
async def create_categorisation(
    user: CurrentUserDep,
    service: CategorisationRunServiceDep,
    response: Response,
    data: RequestCategorisationCreate | None = None,
) -> ResponseCategorisationRun:
    """Start tagging your rows in the background; 200 with the run if one is going."""
    scope = "untagged" if data is None else data.scope
    run, is_new = await service.start(owner_id=user.id, token=user.token, scope=scope)
    if not is_new:
        response.status_code = 200
    return _categorisation_response(run=run)


@router.get("/categorisations", response_model=list[ResponseCategorisationRun])
async def list_categorisations(
    user: CurrentUserDep, service: CategorisationRunServiceDep
) -> list[ResponseCategorisationRun]:
    """List your categorisation runs, newest first."""
    runs = await service.list_runs(owner_id=user.id)
    return [_categorisation_response(run=run) for run in runs]


@router.get("/categorisations/{categorisation_id}", response_model=ResponseCategorisationRun)
async def get_categorisation(run: OwnedCategorisationDep) -> ResponseCategorisationRun:
    """Show the status and counts of a categorisation run."""
    return _categorisation_response(run=run)


@router.get("/transaction-tags", response_model=list[ResponseTransactionTag])
async def list_transaction_tags(
    user: CurrentUserDep,
    service: SeverityServiceDep,
    sort: str | None = None,
    category: Annotated[str | None, Query(max_length=CATEGORY_NAME_MAX_LENGTH)] = None,
    certainty: CertaintyFilter | None = None,
) -> list[ResponseTransactionTag]:
    """List your categorised rows with their severity, filtered by category or certainty."""
    tags = await service.list_rated_tags(
        owner_id=user.id, token=user.token, sort=sort, category=category, certainty=certainty
    )
    return [_tag_response(tag=tag) for tag in tags]


def _category_response(category: SpendingCategory) -> ResponseSpendingCategory:
    return ResponseSpendingCategory.model_validate(category, from_attributes=True)


@router.get("/categories", response_model=list[ResponseSpendingCategory])
async def list_categories(
    user: CurrentUserDep, service: TransactionTagServiceDep
) -> list[ResponseSpendingCategory]:
    """List the categories a booking can get: the built-in ones and your own."""
    categories = await service.list_categories(owner_id=user.id)
    return [_category_response(category=category) for category in categories]


@router.post("/categories", response_model=ResponseSpendingCategory, status_code=201)
async def create_category(
    data: RequestSpendingCategoryCreate, user: CurrentUserDep, service: TransactionTagServiceDep
) -> ResponseSpendingCategory:
    """Add a spending category of your own."""
    category = await service.create_category(owner_id=user.id, data=data)
    return _category_response(category=category)


@router.post("/category-corrections", response_model=ResponseCategoryCorrection, status_code=201)
async def create_category_correction(
    data: RequestCategoryCorrectionCreate, user: CurrentUserDep, service: TransactionTagServiceDep
) -> ResponseCategoryCorrection:
    """Set your category for every booking of a payee, or for one booking."""
    result = await service.create_correction(owner_id=user.id, token=user.token, data=data)
    return _correction_response(result=result)


@router.get("/category-summaries", response_model=list[ResponseCategorySummary])
async def list_category_summaries(
    user: CurrentUserDep,
    service: TransactionTagServiceDep,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
) -> list[ResponseCategorySummary]:
    """Sum your spending per category in a period, with how sure each category is."""
    summaries = await service.list_summaries(
        owner_id=user.id, token=user.token, from_date=from_date, to_date=to_date
    )
    return [_summary_response(summary=summary) for summary in summaries]


def _correction_response(result: CategoryCorrectionResult) -> ResponseCategoryCorrection:
    return ResponseCategoryCorrection.model_validate(result, from_attributes=True)


def _summary_response(summary: CategorySummary) -> ResponseCategorySummary:
    return ResponseCategorySummary.model_validate(summary, from_attributes=True)


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
