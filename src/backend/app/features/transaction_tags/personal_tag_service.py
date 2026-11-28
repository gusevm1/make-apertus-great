import asyncio
import logging
import re
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from app.clients.apertus import ApertusClient, Model
from app.core.errors import ConflictError, NotFoundError, UpstreamError
from app.features.ledger.schemas import LedgerRow
from app.features.ledger.service import LedgerService
from app.features.transaction_tags.goals import read_goal_hints
from app.features.transaction_tags.prompts import assign_tags_prompt, infer_tags_prompt
from app.features.transaction_tags.repository import (
    PersonalTagAssignmentRepository,
    PersonalTagEvaluationRepository,
    PersonalTagRepository,
    TransactionTagRepository,
)
from app.features.transaction_tags.schemas import (
    MAX_INFERRED_TAGS,
    TAG_DESCRIPTION_MAX_LENGTH,
    TAG_NAME_MAX_LENGTH,
    AssignedRow,
    BatchPersonalTags,
    InferredTags,
    PersonalTag,
    PersonalTagAssignment,
    PersonalTagSummary,
    Progress,
    RequestPersonalTagAssignmentCreate,
    RequestPersonalTagCreate,
    RequestPersonalTagUpdate,
)

logger = logging.getLogger(__name__)

BATCH_SIZE = 50
# As long as a categorisation batch: a busy gateway takes over 100 s for 25 rows.
ASSIGN_TIMEOUT_SECONDS = 180
PAYEE_TEXT_LENGTH = 40
MAX_PARALLEL_BATCHES = 16
SPENDING_DAYS = 365
PAYEES_PER_CATEGORY = 5
# Spending rows in these categories, or in a foreign currency, go to Apertus whatever the tags say.
CANDIDATE_CATEGORIES = frozenset({"leisure_travel", "children"})
ASSIGNABLE_KINDS = ("spending", "own_transfer")


class PersonalTagService:
    def __init__(
        self,
        tags: TransactionTagRepository,
        personal: PersonalTagRepository,
        assignments: PersonalTagAssignmentRepository,
        evaluations: PersonalTagEvaluationRepository,
        ledger: LedgerService,
        apertus: ApertusClient,
    ) -> None:
        self.tags = tags
        self.personal = personal
        self.assignments = assignments
        self.evaluations = evaluations
        self.ledger = ledger
        self.apertus = apertus

    async def get_tag(self, tag_id: UUID, owner_id: UUID) -> PersonalTag:
        tag = await self.personal.get_owned(tag_id=tag_id, owner_id=owner_id)
        if tag is None:
            raise NotFoundError(f"No personal tag '{tag_id}'")
        return tag

    async def list_tags(self, owner_id: UUID, token: str) -> list[PersonalTagSummary]:
        rows = await self.ledger.list_rows(token=token)
        return await self._summaries(owner_id=owner_id, rows=rows)

    async def create_tag(
        self, owner_id: UUID, token: str, data: RequestPersonalTagCreate
    ) -> PersonalTagSummary:
        name = data.name.strip()
        if await self.personal.name_taken(owner_id=owner_id, name=name):
            raise ConflictError(f"You have a tag '{name}' already")
        tag = await self.personal.create(
            owner_id=owner_id,
            name=name,
            description=_one_line(text=data.description),
            set_by="customer",
            model=None,
            confirmed=True,
        )
        return await self._summary_of(tag=tag, token=token)

    async def update_tag(
        self, tag: PersonalTag, token: str, data: RequestPersonalTagUpdate
    ) -> PersonalTagSummary:
        cleaned: dict[str, str] = {}
        if data.name is not None:
            cleaned["name"] = data.name.strip()
            if await self.personal.name_taken(
                owner_id=tag.owner_id, name=cleaned["name"], except_id=tag.id
            ):
                raise ConflictError(f"You have a tag '{cleaned['name']}' already")
        if data.description is not None:
            cleaned["description"] = _one_line(text=data.description)
        data = RequestPersonalTagUpdate(**cleaned)
        updated = await self.personal.update(entity_id=tag.id, data=data)
        if updated is None:
            raise NotFoundError(f"No personal tag '{tag.id}'")
        return await self._summary_of(tag=updated, token=token)

    async def delete_tag(self, tag: PersonalTag) -> None:
        await self.personal.delete(entity_id=tag.id)

    async def list_assigned_rows(self, tag: PersonalTag, token: str) -> list[AssignedRow]:
        rows = {(row.source, row.id): row for row in await self.ledger.list_rows(token=token)}
        assignments = await self.assignments.list_for_tag(tag_id=tag.id)
        return [
            _assigned_row(
                assignment=assignment, row=rows[(assignment.row_source, assignment.row_id)]
            )
            for assignment in assignments
            if (assignment.row_source, assignment.row_id) in rows
        ]

    async def create_assignment(
        self, tag: PersonalTag, token: str, data: RequestPersonalTagAssignmentCreate
    ) -> AssignedRow:
        """Put one spending or own-transfer row of the customer under the tag."""
        rows = await self.ledger.list_rows(token=token)
        row = next(
            (
                row
                for row in rows
                if row.source == data.row_source
                and row.id == data.row_id
                and row.kind in ASSIGNABLE_KINDS
            ),
            None,
        )
        if row is None:
            raise NotFoundError(f"No spending or own-transfer row '{data.row_id}'")
        created = await self.assignments.create_missing(
            values=[
                {
                    "tag_id": tag.id,
                    "owner_id": tag.owner_id,
                    "row_source": row.source,
                    "row_id": row.id,
                    "set_by": "customer",
                    "model": None,
                    "confirmed": True,
                }
            ]
        )
        if not created:
            raise ConflictError(f"Row '{data.row_id}' is under '{tag.name}' already")
        return _assigned_row(assignment=created[0], row=row)

    async def delete_assignment(self, tag: PersonalTag, assignment_id: UUID) -> None:
        if not await self.assignments.delete_in_tag(assignment_id=assignment_id, tag_id=tag.id):
            raise NotFoundError(f"No assignment '{assignment_id}' under '{tag.name}'")

    async def create_inference(
        self, owner_id: UUID, token: str, progress: Progress | None = None
    ) -> list[PersonalTagSummary]:
        """Infer tags once, then assign the candidate rows that no earlier run has judged."""
        rows = await self.ledger.list_rows(token=token)
        tags = await self.personal.list_for_owner(owner_id=owner_id)
        evaluated = await self.evaluations.list_row_keys(owner_id=owner_id)
        if not evaluated and all(tag.set_by != "model" for tag in tags):
            await self._infer_tags(owner_id=owner_id, token=token, rows=rows)
            tags = await self.personal.list_for_owner(owner_id=owner_id)
        if tags:
            await self._assign_rows(
                owner_id=owner_id, rows=rows, tags=tags, evaluated=evaluated, progress=progress
            )
        return await self._summaries(owner_id=owner_id, rows=rows)

    async def _infer_tags(self, owner_id: UUID, token: str, rows: list[LedgerRow]) -> None:
        account_names, transfers = await read_goal_hints(ledger=self.ledger, token=token)
        today = await self.ledger.get_today()
        categories = await self.tags.list_categories(owner_id=owner_id)
        result = await self.apertus.structured(
            messages=infer_tags_prompt(
                account_names=account_names,
                transfer_texts=transfers,
                spending=_top_payees(rows=rows, categories=categories, since=today),
                max_tags=MAX_INFERRED_TAGS,
            ),
            schema=InferredTags,
            model=Model.SMART,
            purpose="infer_personal_tags",
        )
        # The first proposal per name counts; at most MAX_INFERRED_TAGS, cut to length.
        proposals: dict[str, dict[str, object]] = {}
        for proposal in result.content.tags:
            name = proposal.name.strip()[:TAG_NAME_MAX_LENGTH]
            if name == "" or name.lower() in proposals or len(proposals) == MAX_INFERRED_TAGS:
                continue
            proposals[name.lower()] = {
                "owner_id": owner_id,
                "name": name,
                "description": _one_line(text=proposal.description or ""),
                "set_by": "model",
                "model": result.model,
            }
        await self.personal.create_missing(values=list(proposals.values()))

    async def _assign_rows(
        self,
        owner_id: UUID,
        rows: list[LedgerRow],
        tags: list[PersonalTag],
        evaluated: set[tuple[str, str]],
        progress: Progress | None,
    ) -> None:
        assigned = await self.assignments.list_for_owner(owner_id=owner_id)
        decided = evaluated | {(item.row_source, item.row_id) for item in assigned}
        categories = await self.tags.list_categories(owner_id=owner_id)
        candidates = [
            row
            for row in _candidate_rows(rows=rows, categories=categories, tags=tags)
            if (row.source, row.id) not in decided
        ]
        batches = [
            candidates[start : start + BATCH_SIZE]
            for start in range(0, len(candidates), BATCH_SIZE)
        ]
        semaphore = asyncio.Semaphore(MAX_PARALLEL_BATCHES)
        calls = [
            asyncio.create_task(
                self._assign_batch(
                    tags=tags, rows=batch, categories=categories, semaphore=semaphore
                )
            )
            for batch in batches
        ]
        failed_batches = 0
        # Written one at a time as they finish: one session, and a crash keeps finished batches.
        for finished, call in enumerate(asyncio.as_completed(calls), start=1):
            answered = await call
            if progress is not None:
                await progress(finished, len(batches))
            if answered is None:
                failed_batches += 1
                continue
            model, judged = answered
            await self.assignments.create_missing(
                values=[
                    {
                        "tag_id": tag.id,
                        "owner_id": owner_id,
                        "row_source": row.source,
                        "row_id": row.id,
                        "set_by": "model",
                        "model": model,
                    }
                    for row, row_tags in judged
                    for tag in row_tags
                ]
            )
            await self.evaluations.create_missing(
                values=[
                    {"owner_id": owner_id, "row_source": row.source, "row_id": row.id}
                    for row, _ in judged
                ]
            )
        if failed_batches > 0:
            logger.error(
                "Personal tags: %s of %s batches failed for %s",
                failed_batches,
                len(batches),
                owner_id,
            )
        if batches and failed_batches == len(batches):
            raise UpstreamError("Apertus judged no batch")

    async def _assign_batch(
        self,
        tags: list[PersonalTag],
        rows: list[LedgerRow],
        categories: dict[tuple[str, str], str],
        semaphore: asyncio.Semaphore,
    ) -> tuple[str, list[tuple[LedgerRow, list[PersonalTag]]]] | None:
        refs = {f"r{number}": row for number, row in enumerate(rows, start=1)}
        ref_categories = {
            ref: categories[(row.source, row.id)]
            for ref, row in refs.items()
            if (row.source, row.id) in categories
        }
        async with semaphore:
            try:
                result = await self.apertus.structured(
                    messages=assign_tags_prompt(tags=tags, rows=refs, categories=ref_categories),
                    schema=BatchPersonalTags,
                    model=Model.SMART,
                    purpose="assign_personal_tags",
                    timeout_seconds=ASSIGN_TIMEOUT_SECONDS,
                )
            except UpstreamError:
                return None
        by_name = {tag.name.lower(): tag for tag in tags}
        # The first answer per ref counts; unknown refs and tag names are dropped.
        judged: dict[str, list[PersonalTag]] = {}
        for answer in result.content.rows:
            if answer.ref not in refs or answer.ref in judged:
                continue
            names = {name.strip().lower() for name in answer.tags or []}
            judged[answer.ref] = [tag for key, tag in by_name.items() if key in names]
        return result.model, [(refs[ref], row_tags) for ref, row_tags in judged.items()]

    async def _summary_of(self, tag: PersonalTag, token: str) -> PersonalTagSummary:
        rows = await self.ledger.list_rows(token=token)
        assignments = await self.assignments.list_for_tag(tag_id=tag.id)
        return _summary(tag=tag, assignments=assignments, rows=_by_key(rows=rows))

    async def _summaries(self, owner_id: UUID, rows: list[LedgerRow]) -> list[PersonalTagSummary]:
        tags = await self.personal.list_for_owner(owner_id=owner_id)
        by_tag: dict[UUID, list[PersonalTagAssignment]] = defaultdict(list)
        for assignment in await self.assignments.list_for_owner(owner_id=owner_id):
            by_tag[assignment.tag_id].append(assignment)
        by_key = _by_key(rows=rows)
        return [_summary(tag=tag, assignments=by_tag[tag.id], rows=by_key) for tag in tags]


def _by_key(rows: list[LedgerRow]) -> dict[tuple[str, str], LedgerRow]:
    return {(row.source, row.id): row for row in rows}


def _one_line(text: str) -> str:
    return " ".join(text.split())[:TAG_DESCRIPTION_MAX_LENGTH]


def _assigned_row(assignment: PersonalTagAssignment, row: LedgerRow) -> AssignedRow:
    return AssignedRow(
        **assignment.model_dump(),
        kind=row.kind,
        date=row.date,
        text=row.text,
        amount_chf=row.amount_chf,
    )


def _summary(
    tag: PersonalTag,
    assignments: list[PersonalTagAssignment],
    rows: dict[tuple[str, str], LedgerRow],
) -> PersonalTagSummary:
    assigned = [
        row
        for assignment in assignments
        if (row := rows.get((assignment.row_source, assignment.row_id))) is not None
    ]
    spending = [row for row in assigned if row.kind == "spending"]
    # Money saved toward the tag: the outgoing leg of an own transfer, not the credit on the pot.
    own_transfers = [row for row in assigned if row.kind == "own_transfer" and row.amount_chf < 0]
    return PersonalTagSummary(
        **tag.model_dump(),
        spending_count=len(spending),
        spending_total_chf=-sum((row.amount_chf for row in spending), Decimal(0)),
        own_transfer_count=len(own_transfers),
        own_transfer_total_chf=-sum((row.amount_chf for row in own_transfers), Decimal(0)),
    )


def _top_payees(
    rows: list[LedgerRow], categories: dict[tuple[str, str], str], since: date
) -> dict[str, list[str]]:
    start = since - timedelta(days=SPENDING_DAYS)
    totals: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for row in rows:
        category = categories.get((row.source, row.id))
        if category is None or row.kind != "spending" or row.date <= start:
            continue
        payee = row.counterparty or row.text[:PAYEE_TEXT_LENGTH]
        totals[category][payee] -= row.amount_chf
    return {
        category: [
            f"{payee} {total}"
            for payee, total in sorted(payees.items(), key=lambda item: -item[1])[
                :PAYEES_PER_CATEGORY
            ]
        ]
        for category, payees in sorted(totals.items())
    }


def _candidate_rows(
    rows: list[LedgerRow], categories: dict[tuple[str, str], str], tags: list[PersonalTag]
) -> list[LedgerRow]:
    """Outgoing own transfers, plus spending related to a tag by category, currency or name."""
    words = {word for tag in tags for word in re.findall(r"\w{3,}", tag.name.casefold())}
    candidates = []
    for row in rows:
        if row.kind == "own_transfer" and row.amount_chf < 0:
            candidates.append(row)
            continue
        if row.kind != "spending":
            continue
        haystack = f"{row.text} {row.counterparty or ''}".casefold()
        if (
            categories.get((row.source, row.id)) in CANDIDATE_CATEGORIES
            or row.original_currency not in (None, "CHF")
            or any(word in haystack for word in words)
        ):
            candidates.append(row)
    return candidates
