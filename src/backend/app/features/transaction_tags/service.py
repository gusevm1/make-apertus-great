import asyncio
from uuid import UUID

from app.clients.apertus import ApertusClient, Model
from app.core.errors import UpstreamError
from app.features.ledger.schemas import LedgerRow
from app.features.ledger.service import LedgerService
from app.features.transaction_tags.prompts import categorise_prompt
from app.features.transaction_tags.repository import TransactionTagRepository
from app.features.transaction_tags.schemas import (
    CATEGORIES,
    BatchCategories,
    Categorisation,
    TransactionTag,
)

BATCH_SIZE = 50
MAX_PARALLEL_BATCHES = 8


class TransactionTagService:
    def __init__(
        self, tags: TransactionTagRepository, ledger: LedgerService, apertus: ApertusClient
    ) -> None:
        self.tags = tags
        self.ledger = ledger
        self.apertus = apertus

    async def list_tags(self, owner_id: UUID, sort: str | None = None) -> list[TransactionTag]:
        return await self.tags.list(sort=sort, owner_id=owner_id)

    async def create_categorisation(self, owner_id: UUID, token: str) -> Categorisation:
        """Give every untagged spending row a category: by rule for loans, else by Apertus."""
        ledger_rows = await self.ledger.list_rows(token=token)
        spending = [row for row in ledger_rows if row.kind == "spending"]
        tagged = await self.tags.list_row_keys(owner_id=owner_id)
        untagged = [row for row in spending if (row.source, row.id) not in tagged]

        by_rule = [row for row in untagged if row.loan_id is not None]
        by_model = [row for row in untagged if row.loan_id is None]
        tagged_by_rule = await self.tags.create_many(
            values=[
                _values(owner_id=owner_id, row=row, category="loan_leasing", model=None)
                for row in by_rule
            ]
        )

        semaphore = asyncio.Semaphore(MAX_PARALLEL_BATCHES)
        batches = [
            by_model[start : start + BATCH_SIZE] for start in range(0, len(by_model), BATCH_SIZE)
        ]
        calls = [
            asyncio.create_task(self._categorise_batch(rows=batch, semaphore=semaphore))
            for batch in batches
        ]
        tagged_by_model = 0
        # Written one at a time as they finish: one session, and a crash keeps finished batches.
        for call in asyncio.as_completed(calls):
            tagged_by_model += await self.tags.create_many(
                values=[
                    _values(owner_id=owner_id, row=row, category=category, model=model)
                    for row, category, model in await call
                ]
            )
        return Categorisation(
            tagged_by_rule=tagged_by_rule,
            tagged_by_model=tagged_by_model,
            already_tagged=len(spending) - len(untagged),
            skipped=len(by_model) - tagged_by_model,
        )

    async def _categorise_batch(
        self, rows: list[LedgerRow], semaphore: asyncio.Semaphore
    ) -> list[tuple[LedgerRow, str, str]]:
        refs = {f"r{number}": row for number, row in enumerate(rows, start=1)}
        async with semaphore:
            try:
                result = await self.apertus.structured(
                    messages=categorise_prompt(rows=refs),
                    schema=BatchCategories,
                    model=Model.SMART,
                    purpose="categorise_spending",
                )
            except UpstreamError:
                return []
        # The first answer per ref counts; unknown refs and categories are dropped.
        answers: dict[str, str] = {}
        for answer in result.content.rows:
            if answer.ref in refs and answer.category in CATEGORIES:
                answers.setdefault(answer.ref, answer.category)
        return [(refs[ref], category, result.model) for ref, category in answers.items()]


def _values(owner_id: UUID, row: LedgerRow, category: str, model: str | None) -> dict[str, object]:
    return {
        "owner_id": owner_id,
        "row_source": row.source,
        "row_id": row.id,
        "category": category,
        "category_set_by": "rule" if model is None else "model",
        "category_model": model,
    }
