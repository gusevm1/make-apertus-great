from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from app.core.errors import BadRequestError
from app.features.ledger.schemas import LedgerRow
from app.features.ledger.service import LedgerService
from app.features.transaction_tags.personal_tag_service import PersonalTagService
from app.features.transaction_tags.schemas import (
    NO_PERSONAL_TAG,
    NOT_CATEGORISED,
    RatedTransactionTag,
    SpendingGroup,
    SpendingSums,
    SumSpendingArgs,
)
from app.features.transaction_tags.severity_service import SeverityService

UNCERTAIN = {"low", None}


class SpendingService:
    def __init__(
        self, ledger: LedgerService, severities: SeverityService, personal: PersonalTagService
    ) -> None:
        self.ledger = ledger
        self.severities = severities
        self.personal = personal

    async def sum_spending(self, owner_id: UUID, token: str, args: SumSpendingArgs) -> SpendingSums:
        """Spending in a period per category, personal tag or severity, with its uncertain rows."""
        rows = [
            row
            for row in await self.ledger.list_rows(token=token)
            if (args.date_from is None or row.date >= args.date_from)
            and (args.date_to is None or row.date <= args.date_to)
        ]
        rated = {
            (tag.row_source, tag.row_id): tag
            for tag in await self.severities.list_rated_tags(owner_id=owner_id, token=token)
        }
        tag_names = await self._tag_names(owner_id=owner_id, token=token, args=args)
        spending = [
            row
            for row in rows
            if row.kind == "spending"
            and _passes(row=row, args=args, rated=rated, tag_names=tag_names)
        ]
        grouped: dict[str, list[LedgerRow]] = defaultdict(list)
        for row in spending:
            for group in _groups(row=row, args=args, rated=rated, tag_names=tag_names):
                grouped[group].append(row)
        # The outgoing side of a transfer to a tag's savings, reported apart from spending (#47).
        saved: dict[str, list[LedgerRow]] = defaultdict(list)
        if args.group_by == "personal_tag":
            for row in rows:
                if row.kind == "own_transfer" and row.amount_chf < 0:
                    for name in tag_names.get((row.source, row.id), []):
                        if (
                            args.personal_tag is None
                            or name.casefold() == args.personal_tag.casefold()
                        ):
                            saved[name].append(row)
        names = sorted(
            set(grouped) | set(saved), key=lambda name: _spent(rows=grouped[name]), reverse=True
        )
        groups = [
            SpendingGroup(
                group=name,
                spent_chf=_spent(rows=grouped[name]),
                count=len(grouped[name]),
                uncertain_count=_uncertain(rows=grouped[name], rated=rated),
                saved_chf=None if args.group_by != "personal_tag" else _spent(rows=saved[name]),
            )
            for name in names
        ]
        return SpendingSums(
            group_by=args.group_by,
            spent_chf=_spent(rows=spending),
            count=len(spending),
            uncertain_count=_uncertain(rows=spending, rated=rated),
            groups=groups,
            language=args.language,
            row_ids={name: [row.id for row in grouped[name] + saved[name]] for name in names},
        )

    async def _tag_names(
        self, owner_id: UUID, token: str, args: SumSpendingArgs
    ) -> dict[tuple[str, str], list[str]]:
        if args.group_by != "personal_tag" and args.personal_tag is None:
            return {}
        tags = await self.personal.list_tags(owner_id=owner_id, token=token)
        if args.personal_tag is not None and not any(
            tag.name.casefold() == args.personal_tag.casefold() for tag in tags
        ):
            known = ", ".join(tag.name for tag in tags) or "none"
            raise BadRequestError(
                f"The customer has no personal tag '{args.personal_tag}'. Their tags: {known}."
            )
        names: dict[tuple[str, str], list[str]] = defaultdict(list)
        for tag in tags:
            for assigned in await self.personal.list_assigned_rows(tag=tag, token=token):
                names[(assigned.row_source, assigned.row_id)].append(tag.name)
        return names


def _passes(
    row: LedgerRow,
    args: SumSpendingArgs,
    rated: dict[tuple[str, str], RatedTransactionTag],
    tag_names: dict[tuple[str, str], list[str]],
) -> bool:
    tag = rated.get((row.source, row.id))
    if args.category is not None and (tag is None or tag.category != args.category):
        return False
    if args.severity is not None and (tag is None or tag.severity != args.severity):
        return False
    if args.personal_tag is None:
        return True
    wanted = args.personal_tag.casefold()
    return any(name.casefold() == wanted for name in tag_names.get((row.source, row.id), []))


def _groups(
    row: LedgerRow,
    args: SumSpendingArgs,
    rated: dict[tuple[str, str], RatedTransactionTag],
    tag_names: dict[tuple[str, str], list[str]],
) -> list[str]:
    tag = rated.get((row.source, row.id))
    match args.group_by:
        case "category":
            return [NOT_CATEGORISED if tag is None else tag.category]
        case "severity":
            return [NOT_CATEGORISED if tag is None else tag.severity]
        case "personal_tag":
            names = tag_names.get((row.source, row.id), [])
            if args.personal_tag is not None:
                names = [name for name in names if name.casefold() == args.personal_tag.casefold()]
            return names or [NO_PERSONAL_TAG]


def _spent(rows: list[LedgerRow]) -> Decimal:
    return -sum((row.amount_chf for row in rows), Decimal(0))


def _uncertain(rows: list[LedgerRow], rated: dict[tuple[str, str], RatedTransactionTag]) -> int:
    return sum(
        1
        for row in rows
        if (tag := rated.get((row.source, row.id))) is not None
        and not tag.category_confirmed
        and tag.category_certainty in UNCERTAIN
    )
