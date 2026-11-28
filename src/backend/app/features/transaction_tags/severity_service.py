from collections import Counter
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from app.clients.apertus import ApertusClient, Model
from app.core.errors import BadRequestError, NotFoundError
from app.features.ledger.service import LedgerService
from app.features.transaction_tags.goals import read_goal_hints
from app.features.transaction_tags.prompts import severity_prompt
from app.features.transaction_tags.repository import (
    CustomCategoryRepository,
    SeveritySettingRepository,
    TransactionTagRepository,
)
from app.features.transaction_tags.schemas import (
    SEVERITIES,
    CertaintyFilter,
    RatedTransactionTag,
    RequestSeverityUpdate,
    SeveritySetting,
    category_names,
    category_severities_schema,
)
from app.features.transaction_tags.severity import (
    booking_key,
    effective_severity,
    normalise_payee,
    payee_key,
)

TOTALS_DAYS = 365


class SeverityService:
    def __init__(
        self,
        tags: TransactionTagRepository,
        severities: SeveritySettingRepository,
        custom: CustomCategoryRepository,
        ledger: LedgerService,
        apertus: ApertusClient,
    ) -> None:
        self.tags = tags
        self.severities = severities
        self.custom = custom
        self.ledger = ledger
        self.apertus = apertus

    async def list_settings(self, owner_id: UUID) -> list[SeveritySetting]:
        return await self.severities.list_for_owner(owner_id=owner_id)

    async def list_rated_tags(
        self,
        owner_id: UUID,
        token: str,
        sort: str | None = None,
        category: str | None = None,
        certainty: CertaintyFilter | None = None,
    ) -> list[RatedTransactionTag]:
        """Your categorised rows with their ledger fields and the severity each one has now."""
        tags = await self.tags.list(sort=sort, owner_id=owner_id)
        settings = await self.severities.list_for_owner(owner_id=owner_id)
        stored = {(setting.scope, setting.key): setting.severity for setting in settings}
        rows = {(row.source, row.id): row for row in await self.ledger.list_rows(token=token)}
        present = [
            (tag, rows[(tag.row_source, tag.row_id)])
            for tag in tags
            if (tag.row_source, tag.row_id) in rows
        ]
        categories_by_payee: dict[str, Counter[str]] = {}
        for tag, row in present:
            categories_by_payee.setdefault(payee_key(row=row), Counter())[tag.category] += 1
        rated = []
        for tag, row in present:
            tag_certainty = "unknown" if tag.category_certainty is None else tag.category_certainty
            if category is not None and tag.category != category:
                continue
            if certainty is not None and (tag.category_confirmed or tag_certainty != certainty):
                continue
            payee = payee_key(row=row)
            severity, source = effective_severity(
                category=tag.category,
                booking=booking_key(row_source=tag.row_source, row_id=tag.row_id),
                payee=payee,
                stored=stored,
            )
            rated.append(
                RatedTransactionTag(
                    **tag.model_dump(),
                    severity=severity,
                    severity_source=source,
                    date=row.date,
                    text=row.text,
                    payee=payee,
                    amount_chf=abs(row.amount_chf),
                    payee_usual_category=_most_common(counts=categories_by_payee[payee]),
                )
            )
        return rated

    async def create_proposal(self, owner_id: UUID, token: str) -> list[SeveritySetting]:
        """Have Apertus rate the categories still without a severity; returns the stored ones."""
        settings = await self.severities.list_for_owner(owner_id=owner_id)
        rated = {setting.key for setting in settings if setting.scope == "category"}
        missing = [
            category
            for category in await self._known_categories(owner_id=owner_id)
            if category not in rated
        ]
        if missing:
            await self._propose(owner_id=owner_id, token=token, missing=missing)
            settings = await self.severities.list_for_owner(owner_id=owner_id)
        return [setting for setting in settings if setting.scope == "category"]

    async def update_setting(
        self, owner_id: UUID, token: str, data: RequestSeverityUpdate
    ) -> SeveritySetting:
        """Set the customer's own severity for a category, a payee or one booking."""
        key = data.key
        if data.scope == "category":
            known = await self._known_categories(owner_id=owner_id)
            if key not in known:
                raise BadRequestError(f"Unknown category '{key}'. Allowed: {', '.join(known)}")
        if data.scope == "payee":
            key = normalise_payee(name=key)
            if key == "":
                raise BadRequestError("A payee key cannot be empty")
        if data.scope == "booking":
            rows = await self.ledger.list_rows(token=token)
            if key not in {
                booking_key(row_source=row.source, row_id=row.id)
                for row in rows
                if row.kind == "spending"
            }:
                raise NotFoundError(f"No spending booking '{key}'")
        return await self.severities.upsert(
            values={
                "owner_id": owner_id,
                "scope": data.scope,
                "key": key,
                "severity": data.severity,
                "set_by": "customer",
                "model": None,
                "confirmed": True,
                "reason": None,
            }
        )

    async def _known_categories(self, owner_id: UUID) -> list[str]:
        return category_names(custom=await self.custom.list_for_owner(owner_id=owner_id))

    async def _propose(self, owner_id: UUID, token: str, missing: list[str]) -> None:
        account_names, transfers = await read_goal_hints(ledger=self.ledger, token=token)
        today = await self.ledger.get_today()
        rows = await self.ledger.list_rows(token=token)
        categories = await self.tags.list_categories(owner_id=owner_id)

        totals: dict[str, Decimal] = {}
        since = today - timedelta(days=TOTALS_DAYS)
        for row in rows:
            category = categories.get((row.source, row.id))
            if category is not None and row.kind == "spending" and row.date > since:
                totals[category] = totals.get(category, Decimal(0)) - row.amount_chf
        result = await self.apertus.structured(
            messages=severity_prompt(
                account_names=account_names,
                transfer_texts=transfers,
                totals={category: str(total) for category, total in sorted(totals.items())},
                categories=missing,
            ),
            schema=category_severities_schema(categories=missing),
            model=Model.SMART,
            purpose="propose_category_severity",
        )
        # The first answer per category counts; unknown categories and severities are dropped.
        answers: dict[str, tuple[str, str]] = {}
        for answer in result.content.categories:
            if answer.category in missing and answer.severity in SEVERITIES:
                answers.setdefault(answer.category, (answer.severity, answer.reason))
        await self.severities.create_missing(
            values=[
                {
                    "owner_id": owner_id,
                    "scope": "category",
                    "key": category,
                    "severity": severity,
                    "set_by": "model",
                    "model": result.model,
                    "reason": reason,
                }
                for category, (severity, reason) in answers.items()
            ]
        )


def _most_common(counts: Counter[str]) -> str:
    """The category with the most rows; a tie goes to the name first in the alphabet."""
    return min(counts, key=lambda category: (-counts[category], category))
