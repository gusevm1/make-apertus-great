import asyncio
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.clients.apertus import ApertusClient, Model
from app.core.errors import NotFoundError, UpstreamError
from app.features.ledger.schemas import LedgerRow
from app.features.ledger.service import LedgerService
from app.features.transaction_tags.prompts import categorise_prompt
from app.features.transaction_tags.repository import (
    CategoryCorrectionRepository,
    TransactionTagRepository,
)
from app.features.transaction_tags.schemas import (
    CATEGORIES,
    CERTAINTIES,
    BatchCategories,
    Categorisation,
    CategoryCorrection,
    CategoryCorrectionResult,
    CategorySummary,
    RequestCategoryCorrectionCreate,
    RowCategory,
    SetBy,
)
from app.features.transaction_tags.severity import booking_key, normalise_payee, payee_key

BATCH_SIZE = 50
MAX_PARALLEL_BATCHES = 16
MAX_CORRECTION_EXAMPLES = 30


class TransactionTagService:
    def __init__(
        self,
        tags: TransactionTagRepository,
        corrections: CategoryCorrectionRepository,
        ledger: LedgerService,
        apertus: ApertusClient,
    ) -> None:
        self.tags = tags
        self.corrections = corrections
        self.ledger = ledger
        self.apertus = apertus

    async def create_categorisation(self, owner_id: UUID, token: str) -> Categorisation:
        """Give every untagged spending row a category: by rule, by correction, else by Apertus."""
        ledger_rows = await self.ledger.list_rows(token=token)
        spending = [row for row in ledger_rows if row.kind == "spending"]
        tagged = await self.tags.list_row_keys(owner_id=owner_id)
        untagged = [row for row in spending if (row.source, row.id) not in tagged]

        corrections = await self.corrections.list_newest(owner_id=owner_id)
        corrected = {correction.payee: correction.category for correction in corrections}
        by_rule = [row for row in untagged if row.loan_id is not None]
        by_correction = [
            row for row in untagged if row.loan_id is None and payee_key(row=row) in corrected
        ]
        by_model = [
            row for row in untagged if row.loan_id is None and payee_key(row=row) not in corrected
        ]
        tagged_by_rule = await self.tags.create_many(
            values=[
                _fixed_values(owner_id=owner_id, row=row, category="loan_leasing", set_by="rule")
                for row in by_rule
            ]
        )
        tagged_by_correction = await self.tags.create_many(
            values=[
                _fixed_values(
                    owner_id=owner_id,
                    row=row,
                    category=corrected[payee_key(row=row)],
                    set_by="customer",
                )
                for row in by_correction
            ]
        )
        examples = corrections[:MAX_CORRECTION_EXAMPLES]

        semaphore = asyncio.Semaphore(MAX_PARALLEL_BATCHES)
        batches = [
            by_model[start : start + BATCH_SIZE] for start in range(0, len(by_model), BATCH_SIZE)
        ]
        calls = [
            asyncio.create_task(
                self._categorise_batch(rows=batch, examples=examples, semaphore=semaphore)
            )
            for batch in batches
        ]
        tagged_by_model = 0
        failed_batches = 0
        # Written one at a time as they finish: one session, and a crash keeps finished batches.
        for call in asyncio.as_completed(calls):
            answered = await call
            if answered is None:
                failed_batches += 1
                continue
            tagged_by_model += await self.tags.create_many(
                values=[
                    _model_values(owner_id=owner_id, row=row, answer=answer, model=model)
                    for row, answer, model in answered
                ]
            )
        if batches and failed_batches == len(batches):
            raise UpstreamError("Apertus categorised no batch")
        return Categorisation(
            tagged_by_rule=tagged_by_rule,
            tagged_by_correction=tagged_by_correction,
            tagged_by_model=tagged_by_model,
            already_tagged=len(spending) - len(untagged),
            skipped=len(by_model) - tagged_by_model,
        )

    async def create_correction(
        self, owner_id: UUID, token: str, data: RequestCategoryCorrectionCreate
    ) -> CategoryCorrectionResult:
        """Set the customer's category on all rows of a payee, also later ones, or one booking."""
        spending = [
            row for row in await self.ledger.list_rows(token=token) if row.kind == "spending"
        ]
        key = normalise_payee(name=data.key) if data.scope == "payee" else data.key
        if data.scope == "payee":
            rows = [row for row in spending if payee_key(row=row) == key]
        else:
            rows = [
                row for row in spending if booking_key(row_source=row.source, row_id=row.id) == key
            ]
        if not rows:
            raise NotFoundError(f"No spending {data.scope} '{data.key}'")
        if data.scope == "payee":
            await self.corrections.upsert(owner_id=owner_id, payee=key, category=data.category)
        changed = await self.tags.upsert_categories(
            values=[
                _fixed_values(owner_id=owner_id, row=row, category=data.category, set_by="customer")
                for row in rows
            ]
        )
        return CategoryCorrectionResult(
            scope=data.scope, key=key, category=data.category, rows_changed=changed
        )

    async def list_summaries(
        self, owner_id: UUID, token: str, from_date: date | None, to_date: date | None
    ) -> list[CategorySummary]:
        """Per category in the period: what its spending rows add up to and how sure each one is."""
        tags = {
            (tag.row_source, tag.row_id): tag
            for tag in await self.tags.list_for_owner(owner_id=owner_id)
        }
        summaries: dict[str | None, CategorySummary] = {}
        for row in await self.ledger.list_rows(token=token):
            if row.kind != "spending":
                continue
            if from_date is not None and row.date < from_date:
                continue
            if to_date is not None and row.date > to_date:
                continue
            tag = tags.get((row.source, row.id))
            category = None if tag is None else tag.category
            summary = summaries.setdefault(category, _empty_summary(category=category))
            summary.total_chf -= row.amount_chf
            summary.row_count += 1
            if tag is None or tag.category_confirmed:
                summary.confirmed += 0 if tag is None else 1
                continue
            certainty = "unknown" if tag.category_certainty is None else tag.category_certainty
            setattr(summary, certainty, getattr(summary, certainty) + 1)
        return sorted(summaries.values(), key=lambda summary: summary.total_chf, reverse=True)

    async def _categorise_batch(
        self,
        rows: list[LedgerRow],
        examples: list[CategoryCorrection],
        semaphore: asyncio.Semaphore,
    ) -> list[tuple[LedgerRow, RowCategory, str]] | None:
        refs = {f"r{number}": row for number, row in enumerate(rows, start=1)}
        async with semaphore:
            try:
                result = await self.apertus.structured(
                    messages=categorise_prompt(rows=refs, examples=examples),
                    schema=BatchCategories,
                    model=Model.SMART,
                    purpose="categorise_spending",
                )
            except UpstreamError:
                return None
        # The first answer per ref counts; unknown refs and categories are dropped.
        answers: dict[str, RowCategory] = {}
        for answer in result.content.rows:
            if answer.ref not in refs or answer.category not in CATEGORIES:
                continue
            certainty = answer.certainty if answer.certainty in CERTAINTIES else None
            answers.setdefault(answer.ref, answer.model_copy(update={"certainty": certainty}))
        return [(refs[ref], answer, result.model) for ref, answer in answers.items()]


def _fixed_values(
    owner_id: UUID, row: LedgerRow, category: str, set_by: SetBy
) -> dict[str, object]:
    return {
        "owner_id": owner_id,
        "row_source": row.source,
        "row_id": row.id,
        "category": category,
        "category_set_by": set_by,
        "category_model": None,
        "category_confirmed": set_by == "customer",
        "category_certainty": "high",
    }


def _model_values(
    owner_id: UUID, row: LedgerRow, answer: RowCategory, model: str
) -> dict[str, object]:
    return {
        "owner_id": owner_id,
        "row_source": row.source,
        "row_id": row.id,
        "category": answer.category,
        "category_set_by": "model",
        "category_model": model,
        "category_confirmed": False,
        "category_certainty": answer.certainty,
    }


def _empty_summary(category: str | None) -> CategorySummary:
    return CategorySummary(
        category=category,
        total_chf=Decimal(0),
        row_count=0,
        high=0,
        medium=0,
        low=0,
        unknown=0,
        confirmed=0,
    )
