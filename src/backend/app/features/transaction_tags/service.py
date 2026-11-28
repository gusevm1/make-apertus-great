import asyncio
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.clients.apertus import ApertusClient, Model
from app.core.errors import BadRequestError, ConflictError, NotFoundError, UpstreamError
from app.features.ledger.schemas import LedgerRow
from app.features.ledger.service import LedgerService
from app.features.transaction_tags.prompts import categorise_prompt
from app.features.transaction_tags.repository import (
    CategoryCorrectionRepository,
    CustomCategoryRepository,
    TransactionTagRepository,
)
from app.features.transaction_tags.schemas import (
    CATEGORIES,
    CERTAINTIES,
    NOT_CATEGORISED,
    Categorisation,
    CategorisationScope,
    CategoryCorrection,
    CategoryCorrectionResult,
    CategorySummary,
    CustomCategory,
    Progress,
    RequestCategoryCorrectionCreate,
    RequestSpendingCategoryCreate,
    RowCategory,
    SetBy,
    SpendingCategory,
    TransactionTag,
    batch_categories_schema,
    category_names,
)
from app.features.transaction_tags.severity import booking_key, normalise_payee, payee_key

BATCH_SIZE = 25
# Under load the shared gateway answers 16 parallel batches after more than a minute each.
MAX_PARALLEL_BATCHES = 8
# A batch takes 30 to 50 seconds when the gateway is busy; cut off sooner, it is sent again.
CATEGORISE_TIMEOUT_SECONDS = 150
MAX_CORRECTION_EXAMPLES = 30


class TransactionTagService:
    def __init__(
        self,
        tags: TransactionTagRepository,
        corrections: CategoryCorrectionRepository,
        custom: CustomCategoryRepository,
        ledger: LedgerService,
        apertus: ApertusClient,
    ) -> None:
        self.tags = tags
        self.corrections = corrections
        self.custom = custom
        self.ledger = ledger
        self.apertus = apertus

    async def list_categories(self, owner_id: UUID) -> list[SpendingCategory]:
        """The built-in categories, then the customer's own in the order they were added."""
        custom = await self.custom.list_for_owner(owner_id=owner_id)
        return [
            *(SpendingCategory(name=name, description="", custom=False) for name in CATEGORIES),
            *(
                SpendingCategory(name=category.name, description=category.description, custom=True)
                for category in custom
            ),
        ]

    async def create_category(
        self, owner_id: UUID, data: RequestSpendingCategoryCreate
    ) -> SpendingCategory:
        """Add a spending category of the customer's own; a later run uses it."""
        taken = {name.casefold() for name in await self._known_categories(owner_id=owner_id)}
        if data.name.casefold() in taken | {NOT_CATEGORISED}:
            raise ConflictError(f"There is a category '{data.name}' already")
        created = await self.custom.create_unique(
            owner_id=owner_id, name=data.name, description=data.description
        )
        # A second request with the same name can pass the check before the first is stored.
        if created is None:
            raise ConflictError(f"There is a category '{data.name}' already")
        return SpendingCategory(name=created.name, description=created.description, custom=True)

    async def create_categorisation(
        self,
        owner_id: UUID,
        token: str,
        scope: CategorisationScope = "untagged",
        progress: Progress | None = None,
    ) -> Categorisation:
        """Give spending rows a category: by rule, by correction, else by Apertus.

        `untagged` takes the rows without a category; `unconfirmed` also has Apertus judge again
        what it decided before and the customer has not confirmed.
        """
        ledger_rows = await self.ledger.list_rows(token=token)
        spending = [row for row in ledger_rows if row.kind == "spending"]
        stored = await self.tags.list_for_owner(owner_id=owner_id)
        tagged = {(tag.row_source, tag.row_id) for tag in stored}
        untagged = [row for row in spending if (row.source, row.id) not in tagged]
        redo = {
            (tag.row_source, tag.row_id)
            for tag in stored
            if scope == "unconfirmed" and tag.category_set_by == "model"
        }
        rejudged = [row for row in spending if (row.source, row.id) in redo]

        corrections = await self.corrections.list_newest(owner_id=owner_id)
        custom = await self.custom.list_for_owner(owner_id=owner_id)
        corrected = {correction.payee: correction.category for correction in corrections}
        by_rule = [row for row in untagged if row.loan_id is not None]
        by_correction = [
            row for row in untagged if row.loan_id is None and payee_key(row=row) in corrected
        ]
        by_model = [
            row for row in untagged if row.loan_id is None and payee_key(row=row) not in corrected
        ] + rejudged
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
        examples = _examples(corrections=corrections, tags=stored, rows=spending)
        categories = category_names(custom=custom)
        total = len(by_rule) + len(by_correction) + len(by_model)
        done = len(by_rule) + len(by_correction)
        if progress is not None:
            await progress(done, total)

        semaphore = asyncio.Semaphore(MAX_PARALLEL_BATCHES)
        batches = [
            by_model[start : start + BATCH_SIZE] for start in range(0, len(by_model), BATCH_SIZE)
        ]

        async def categorise(
            batch: list[LedgerRow],
        ) -> tuple[int, list[tuple[LedgerRow, RowCategory, str]] | None]:
            answered = await self._categorise_batch(
                rows=batch,
                examples=examples,
                custom=custom,
                categories=categories,
                semaphore=semaphore,
            )
            return len(batch), answered

        calls = [asyncio.create_task(categorise(batch=batch)) for batch in batches]
        tagged_by_model = 0
        failed_batches = 0
        # Written one at a time as they finish: one session, and a crash keeps finished batches.
        for call in asyncio.as_completed(calls):
            size, answered = await call
            done += size
            if progress is not None:
                await progress(done, total)
            if answered is None:
                failed_batches += 1
                continue
            values = [
                _model_values(owner_id=owner_id, row=row, answer=answer, model=model)
                for row, answer, model in answered
            ]
            # A row judged again replaces its earlier answer; a new one never replaces a tag.
            tagged_by_model += await (
                self.tags.replace_model_categories(values=values)
                if scope == "unconfirmed"
                else self.tags.create_many(values=values)
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
        known = await self._known_categories(owner_id=owner_id)
        if data.category not in known:
            raise BadRequestError(
                f"Unknown category '{data.category}'. Allowed: {', '.join(known)}"
            )
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
            if tag is None:
                continue
            if tag.category_confirmed:
                summary.confirmed += 1
                continue
            certainty = "unknown" if tag.category_certainty is None else tag.category_certainty
            setattr(summary, certainty, getattr(summary, certainty) + 1)
        return sorted(summaries.values(), key=lambda summary: summary.total_chf, reverse=True)

    async def _known_categories(self, owner_id: UUID) -> list[str]:
        return category_names(custom=await self.custom.list_for_owner(owner_id=owner_id))

    async def _categorise_batch(
        self,
        rows: list[LedgerRow],
        examples: list[dict[str, str]],
        custom: list[CustomCategory],
        categories: list[str],
        semaphore: asyncio.Semaphore,
    ) -> list[tuple[LedgerRow, RowCategory, str]] | None:
        refs = {f"r{number}": row for number, row in enumerate(rows, start=1)}
        async with semaphore:
            try:
                result = await self.apertus.structured(
                    messages=categorise_prompt(rows=refs, examples=examples, custom=custom),
                    schema=batch_categories_schema(categories=categories),
                    model=Model.SMART,
                    purpose="categorise_spending",
                    timeout_seconds=CATEGORISE_TIMEOUT_SECONDS,
                )
            except UpstreamError:
                return None
        # The first answer per ref counts; unknown refs and categories are dropped.
        answers: dict[str, RowCategory] = {}
        for answer in result.content.rows:
            if answer.ref not in refs or answer.category not in categories:
                continue
            certainty = answer.certainty if answer.certainty in CERTAINTIES else None
            alternative = (
                answer.alternative
                if answer.alternative in categories and answer.alternative != answer.category
                else None
            )
            answers.setdefault(
                answer.ref,
                answer.model_copy(update={"certainty": certainty, "alternative": alternative}),
            )
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
        "category_alternative": None,
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
        "category_alternative": answer.alternative,
    }


def _examples(
    corrections: list[CategoryCorrection], tags: list[TransactionTag], rows: list[LedgerRow]
) -> list[dict[str, str]]:
    """The customer's newest decisions, per payee and per booking, with a booking text each."""
    by_key = {(row.source, row.id): row for row in rows}
    texts: dict[str, str] = {}
    for row in rows:
        texts.setdefault(payee_key(row=row), row.text)
    corrected = {correction.payee for correction in corrections}
    decisions = [
        (correction.updated_at, correction.payee, texts.get(correction.payee), correction.category)
        for correction in corrections
    ]
    for tag in tags:
        row = by_key.get((tag.row_source, tag.row_id))
        # A payee's own decision already covers its bookings.
        if tag.category_set_by != "customer" or row is None or payee_key(row=row) in corrected:
            continue
        decisions.append((tag.updated_at, payee_key(row=row), row.text, tag.category))
    decisions.sort(key=lambda decision: decision[0], reverse=True)
    return [
        {"payee": payee, "category": category}
        if text is None
        else {"payee": payee, "text": text, "category": category}
        for _, payee, text, category in decisions[:MAX_CORRECTION_EXAMPLES]
    ]


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
