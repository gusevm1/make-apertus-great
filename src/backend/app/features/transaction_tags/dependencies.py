from typing import Annotated
from uuid import UUID

from fastapi import Depends

from app.clients.apertus import ApertusClientDep
from app.core.auth import CurrentUserDep
from app.core.db import SessionDep
from app.features.ledger.dependencies import LedgerServiceDep
from app.features.transaction_tags.categorisation_runs import CategorisationRunService
from app.features.transaction_tags.personal_tag_service import PersonalTagService
from app.features.transaction_tags.repository import (
    CategorisationRunRepository,
    CategoryCorrectionRepository,
    CustomCategoryRepository,
    PersonalTagAssignmentRepository,
    PersonalTagEvaluationRepository,
    PersonalTagRepository,
    SeveritySettingRepository,
    TransactionTagRepository,
)
from app.features.transaction_tags.schemas import CategorisationRun, PersonalTag
from app.features.transaction_tags.service import TransactionTagService
from app.features.transaction_tags.severity_service import SeverityService
from app.features.transaction_tags.spending_service import SpendingService


def get_transaction_tag_repo(session: SessionDep) -> TransactionTagRepository:
    return TransactionTagRepository(session=session)


def get_severity_setting_repo(session: SessionDep) -> SeveritySettingRepository:
    return SeveritySettingRepository(session=session)


def get_transaction_tag_service(
    tags: Annotated[TransactionTagRepository, Depends(get_transaction_tag_repo)],
    session: SessionDep,
    ledger: LedgerServiceDep,
    apertus: ApertusClientDep,
) -> TransactionTagService:
    return TransactionTagService(
        tags=tags,
        corrections=CategoryCorrectionRepository(session=session),
        custom=CustomCategoryRepository(session=session),
        ledger=ledger,
        apertus=apertus,
    )


TransactionTagServiceDep = Annotated[TransactionTagService, Depends(get_transaction_tag_service)]


def get_severity_service(
    tags: Annotated[TransactionTagRepository, Depends(get_transaction_tag_repo)],
    severities: Annotated[SeveritySettingRepository, Depends(get_severity_setting_repo)],
    session: SessionDep,
    ledger: LedgerServiceDep,
    apertus: ApertusClientDep,
) -> SeverityService:
    return SeverityService(
        tags=tags,
        severities=severities,
        custom=CustomCategoryRepository(session=session),
        ledger=ledger,
        apertus=apertus,
    )


SeverityServiceDep = Annotated[SeverityService, Depends(get_severity_service)]


def get_personal_tag_service(
    tags: Annotated[TransactionTagRepository, Depends(get_transaction_tag_repo)],
    session: SessionDep,
    ledger: LedgerServiceDep,
    apertus: ApertusClientDep,
) -> PersonalTagService:
    return PersonalTagService(
        tags=tags,
        personal=PersonalTagRepository(session=session),
        assignments=PersonalTagAssignmentRepository(session=session),
        evaluations=PersonalTagEvaluationRepository(session=session),
        ledger=ledger,
        apertus=apertus,
    )


PersonalTagServiceDep = Annotated[PersonalTagService, Depends(get_personal_tag_service)]


async def get_owned_personal_tag(
    tag_id: UUID, user: CurrentUserDep, service: PersonalTagServiceDep
) -> PersonalTag:
    return await service.get_tag(tag_id=tag_id, owner_id=user.id)


OwnedPersonalTagDep = Annotated[PersonalTag, Depends(get_owned_personal_tag)]


def get_spending_service(
    session: SessionDep, ledger: LedgerServiceDep, severities: SeverityServiceDep
) -> SpendingService:
    return SpendingService(
        ledger=ledger,
        severities=severities,
        personal=PersonalTagRepository(session=session),
        assignments=PersonalTagAssignmentRepository(session=session),
    )


SpendingServiceDep = Annotated[SpendingService, Depends(get_spending_service)]


def get_categorisation_run_service(
    session: SessionDep, ledger: LedgerServiceDep, apertus: ApertusClientDep
) -> CategorisationRunService:
    return CategorisationRunService(
        runs=CategorisationRunRepository(session=session), ledger=ledger, apertus=apertus
    )


CategorisationRunServiceDep = Annotated[
    CategorisationRunService, Depends(get_categorisation_run_service)
]


async def get_owned_categorisation(
    categorisation_id: UUID, user: CurrentUserDep, service: CategorisationRunServiceDep
) -> CategorisationRun:
    return await service.get_run(categorisation_id=categorisation_id, owner_id=user.id)


OwnedCategorisationDep = Annotated[CategorisationRun, Depends(get_owned_categorisation)]
