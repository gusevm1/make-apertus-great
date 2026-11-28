import asyncio
import calendar
import re
import statistics
from collections import Counter, defaultdict
from collections.abc import Awaitable, Callable
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal, NamedTuple
from urllib.parse import quote

from pydantic import ValidationError

from app.features.ledger.schemas import PILLAR_3A_LIMITS_CHF, Filters, LedgerRow
from app.features.ledger.service import LedgerService, _chf, _has_words, _month, _shift
from app.features.recurring_payments.service import RecurringPaymentService
from app.features.tiles.schemas import (
    SOURCE_ROWS_MAX,
    TEMPLATES,
    AccountBalancesArgs,
    AccountBalancesPayload,
    AccountRow,
    AllocationPart,
    AnyPayload,
    Args,
    BalancePoint,
    BillArgs,
    BillPayload,
    BillRow,
    BillsUntilPaydayArgs,
    BillsUntilPaydayPayload,
    CardBillArgs,
    CardBillPayload,
    CashflowMonth,
    DueSoonArgs,
    DueSoonPayload,
    ExpectedIncomeArgs,
    ExpectedIncomePayload,
    Flag,
    IncomeAndSpendingArgs,
    IncomeAndSpendingPayload,
    IncomeMonth,
    MerchantRow,
    MerchantSpendingArgs,
    MerchantSpendingPayload,
    MonthlySpendingArgs,
    MonthlySpendingPayload,
    MortgageArgs,
    MortgagePayload,
    NetWorthArgs,
    NetWorthPayload,
    PaydayAlternative,
    PaydayBalanceArgs,
    PaydayBalancePayload,
    Pillar3aArgs,
    Pillar3aPayload,
    PlannedTransfer,
    RegularPaymentRow,
    RegularPaymentsArgs,
    RegularPaymentsPayload,
    SavingsGoalArgs,
    SavingsGoalPayload,
    SecuritiesArgs,
    SecuritiesPayload,
    Source,
    SourceRow,
    SpendingMonth,
    Tranche,
    WorthPart,
)

CENT = Decimal("0.01")
TENTH = Decimal("0.1")
# A salary older than this means the rhythm broke, so no payday can be expected.
SALARY_STALE_DAYS = 40
SALARY_RHYTHM_PAYMENTS = 12
# ponytail: fixed holidays only; add Easter-based ones (Whit Monday moved 25.05.2026) when needed.
FIXED_HOLIDAYS = {(1, 1), (1, 2), (8, 1), (12, 25), (12, 26)}
INCOME_HISTORY_MONTHS = 12
INCOME_MIN_MONTHS = 3
INCOME_WINDOW_MONTHS = 3
# An income that arrives more than this many days after its usual day is late.
LATE_AFTER_DAYS = 7
DUE_SOON_LISTED = 4
BILL_LOOKAHEAD_DAYS = 92
REGULAR_LOOKAHEAD_DAYS = 62
MATURITY_SOON_DAYS = 548
PAYEES_LISTED = 10
MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
GERMAN_MONTHS = dict(
    zip(
        [
            "Januar",
            "Februar",
            "März",
            "April",
            "Mai",
            "Juni",
            "Juli",
            "August",
            "September",
            "Oktober",
            "November",
            "Dezember",
        ],
        MONTHS,
        strict=True,
    )
)
ASSET_CLASSES = {
    "Aktien": "Shares",
    "Obligationen": "Bonds",
    "Immobilien": "Real estate",
    "Rohstoffe": "Commodities",
    "Liquidität": "Cash",
}
CARD_PAYMENT_TYPES = {"debit_card"}
# Swiss amounts such as 7'258 or 12'000.50.
AMOUNT = re.compile(r"CHF\s*(\d{1,3}(?:['’]\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)")
# A legal form and what follows it, such as " AG Liegenschaftsverwaltung".
LEGAL_SUFFIX = re.compile(r"[\s-]+(AG|GmbH|SA|Sàrl|SE|Ltd)\b.*$")


def _for_month(noun: str, word: str) -> str:
    return f"{noun} for {GERMAN_MONTHS[word]}" if word in GERMAN_MONTHS else noun


# The common German payment texts in a few English words; anything else is cut to its first words.
DETAILS: list[tuple[re.Pattern[str], Callable[[re.Match[str]], str | None]]] = [
    (re.compile(r"^Rechnung Nr\b"), lambda match: None),
    (re.compile(r"\bRate (\d+)/(\d+)"), lambda match: f"instalment {match[1]} of {match[2]}"),
    (re.compile(r"\bMiete (\w+)"), lambda match: _for_month(noun="rent", word=match[1])),
    (re.compile(r"\bPrämie (\w+)"), lambda match: _for_month(noun="premium", word=match[1])),
    (re.compile(r"\bVorauszahlung\b"), lambda match: "advance payment"),
    (re.compile(r"\bMobile\b"), lambda match: "mobile"),
    (re.compile(r"\bInternet\b"), lambda match: "internet"),
    (re.compile(r"\bMitgliedschaft\b"), lambda match: "membership"),
    (re.compile(r"\bSparplan\b"), lambda match: "savings plan"),
    (re.compile(r"\bAnzahlung\b"), lambda match: "deposit"),
    (re.compile(r"\bSpende\b"), lambda match: "donation"),
]


class TileError(Exception):
    """A tile that cannot be drawn; the message says why, and what to send instead."""


class Income(NamedTuple):
    usual_day: int
    amount: Decimal
    months: list[IncomeMonth]
    status: Literal["arrived", "not_arrived"]
    rows: list[LedgerRow]


class TileService:
    def __init__(self, ledger: LedgerService, recurring: RecurringPaymentService) -> None:
        self.ledger = ledger
        self.recurring = recurring
        # A board resolves its tiles at once; they share one read of the ledger.
        self._rows: dict[str, asyncio.Future[list[LedgerRow]]] = {}

    def validate_args(self, template: str, args: dict[str, Any]) -> Args:
        """The template's arguments as their model; TileError names what is wrong and the fix."""
        if template not in TEMPLATES:
            raise TileError(f"Unknown template {template}. Use one of: {', '.join(TEMPLATES)}.")
        args_model = TEMPLATES[template][0]
        try:
            return args_model.model_validate(args)
        except ValidationError as error:
            raise TileError(_args_message(template=template, error=error)) from error

    async def resolve(
        self, template: str, args: dict[str, Any], token: str, today: date
    ) -> AnyPayload:
        """Compute a tile from the banking API as it is now; TileError when it shows nothing."""
        validated = self.validate_args(template=template, args=args)
        resolver: Callable[..., Awaitable[AnyPayload]] = getattr(self, f"_{template}")
        return await resolver(args=validated, token=token, today=today)

    def default_title(self, payload: AnyPayload) -> str:
        """The title a tile gets when nobody wrote one, such as "Left on 23.12."."""
        match payload:
            case PaydayBalancePayload():
                return "Left before payday"
            case BillsUntilPaydayPayload():
                return "Bills until payday"
            case DueSoonPayload():
                return f"Due in {payload.days} days"
            case ExpectedIncomePayload():
                return f"From {payload.counterparty.split()[0]}"
            case MerchantSpendingPayload():
                return _merchant_title(payload=payload)
            case SavingsGoalPayload():
                return payload.account_name if len(payload.account_name) <= 24 else "Savings goal"
            case BillPayload():
                return f"Bill, due {_day(day=payload.due)}"
            case NetWorthPayload():
                return "What you own"
            case MonthlySpendingPayload():
                return "Where the money goes"
            case IncomeAndSpendingPayload():
                return "Income and spending"
            case SecuritiesPayload():
                return "Securities"
            case RegularPaymentsPayload():
                return "Regular payments"
            case Pillar3aPayload():
                return f"Pillar 3a, {payload.year}"
            case AccountBalancesPayload():
                return "Your accounts"
            case MortgagePayload():
                return "Mortgage"
            case CardBillPayload():
                return f"{payload.card_name}, {_month_name(month=payload.period)}"

    async def _payday_balance(
        self, args: PaydayBalanceArgs, token: str, today: date
    ) -> PaydayBalancePayload:
        accounts, rows = await asyncio.gather(
            self._accounts(token=token), self._ledger_rows(token=token)
        )
        account = _account(accounts=accounts, account_id=args.account_id)
        payday = _payday(rows=rows, account_id=args.account_id, today=today)
        day_before = payday - timedelta(days=1)
        preview = await self._balance_preview(
            token=token, account_id=args.account_id, date_to=day_before
        )
        today_balance = _chf(amount=preview["current_balance"])
        points = [
            point for point in preview["points"] if date.fromisoformat(point["date"]) <= day_before
        ]
        left = today_balance if not points else _chf(amount=points[-1]["balance"])
        days = (day_before - today).days + 1
        alternative = None
        if args.expected_from is not None:
            income = _income(rows=rows, counterparty=args.expected_from, today=today)
            if income.status == "not_arrived":
                with_income = left + income.amount
                alternative = PaydayAlternative(
                    counterparty=args.expected_from,
                    label=args.expected_label,
                    amount_chf=income.amount,
                    left_chf=with_income,
                    per_day_chf=_per_day(amount=with_income, days=days),
                )
        return PaydayBalancePayload(
            figure_chf=left,
            source=Source(
                label=f"{account['name']} and {_count(count=len(points), noun='upcoming payment')}",
                kind="payments",
                rows=[
                    SourceRow(
                        id=point["source_id"],
                        date=point["date"],
                        text=point["description"],
                        amount_chf=_chf(amount=point["amount"]),
                    )
                    for point in points[:SOURCE_ROWS_MAX]
                ],
                count=len(points),
            ),
            account_name=account["name"],
            payday=payday,
            day_before=day_before,
            days=days,
            per_day_chf=_per_day(amount=left, days=days),
            today=today,
            today_balance_chf=today_balance,
            points=[
                BalancePoint(date=today, balance_chf=today_balance),
                *(
                    BalancePoint(date=point["date"], balance_chf=_chf(amount=point["balance"]))
                    for point in points
                ),
            ],
            upcoming_count=len(points),
            alternative=alternative,
        )

    async def _bills_until_payday(
        self, args: BillsUntilPaydayArgs, token: str, today: date
    ) -> BillsUntilPaydayPayload:
        accounts, rows = await asyncio.gather(
            self._accounts(token=token), self._ledger_rows(token=token)
        )
        account = _account(accounts=accounts, account_id=args.account_id)
        payday = _payday(rows=rows, account_id=args.account_id, today=today)
        day_before = payday - timedelta(days=1)
        upcoming, preview = await asyncio.gather(
            self._upcoming(
                token=token, date_from=today, date_to=day_before, account_id=args.account_id
            ),
            self._balance_preview(token=token, account_id=args.account_id, date_to=day_before),
        )
        payments = upcoming["items"]
        if not payments:
            raise TileError(
                f"No payment leaves {account['name']} before payday on {_day(day=payday)}. "
                "Use due_soon for the payments of the next weeks."
            )
        balances: dict[tuple[str, str], list[Decimal]] = defaultdict(list)
        for point in preview["points"]:
            balances[(point["date"], point["source_id"])].append(_chf(amount=point["balance"]))
        bill_rows = []
        for payment in payments:
            after = balances[(payment["due_date"], payment["source_id"])]
            bill_rows.append(
                _bill_row(payment=payment, balance_after=after.pop(0) if after else None)
            )
        return BillsUntilPaydayPayload(
            figure_chf=_chf(amount=upcoming["total_chf"]),
            source=_payments_source(
                payments=payments,
                label=_count(count=len(payments), noun="upcoming payment"),
            ),
            payday=payday,
            rows=bill_rows,
        )

    async def _due_soon(self, args: DueSoonArgs, token: str, today: date) -> DueSoonPayload:
        upcoming = await self._upcoming(
            token=token, date_from=today, date_to=today + timedelta(days=args.days - 1)
        )
        payments = upcoming["items"]
        if not payments:
            raise TileError(f"Nothing falls due in the next {args.days} days. Try a longer period.")
        by_size = sorted(range(len(payments)), key=lambda index: -payments[index]["amount_chf"])
        listed = sorted(by_size[:DUE_SOON_LISTED])
        return DueSoonPayload(
            figure_chf=_chf(amount=upcoming["total_chf"]),
            source=_payments_source(payments=payments, label=f"All {len(payments)} payments"),
            days=args.days,
            rows=[_bill_row(payment=payments[index], balance_after=None) for index in listed],
            count=len(payments),
        )

    async def _expected_income(
        self, args: ExpectedIncomeArgs, token: str, today: date
    ) -> ExpectedIncomePayload:
        rows = await self._ledger_rows(token=token)
        income = _income(rows=rows, counterparty=args.counterparty, today=today)
        return ExpectedIncomePayload(
            figure_chf=income.amount,
            source=_bookings_source(
                rows=income.rows,
                label=f"{_count(count=len(income.rows), noun='booking')} from {args.counterparty}",
            ),
            counterparty=args.counterparty,
            usual_day=income.usual_day,
            status=income.status,
            months=income.months,
        )

    async def _merchant_spending(
        self, args: MerchantSpendingArgs, token: str, today: date
    ) -> MerchantSpendingPayload:
        date_from, date_to = _period(period=args.period, today=today)
        spending = [row for row in await self._ledger_rows(token=token) if row.kind == "spending"]
        _check_words(rows=spending, words=args.merchants)
        by_merchant: dict[str, list[LedgerRow]] = defaultdict(list)
        for row in spending:
            if not date_from <= row.date <= date_to:
                continue
            merchant = next(
                (name for name in args.merchants if _has_words(row=row, words=[name])), None
            )
            if merchant is not None:
                by_merchant[merchant].append(row)
        if not by_merchant:
            raise TileError(
                f"No payments at {', '.join(args.merchants)} between {_day(day=date_from)} and "
                f"{_day(day=date_to)}. Try period last_3_months."
            )
        totals = {
            merchant: -sum((row.amount_chf for row in group), Decimal(0))
            for merchant, group in by_merchant.items()
        }
        names = sorted(totals, key=lambda name: totals[name], reverse=True)
        largest = totals[names[0]]
        matched = sorted(
            (row for group in by_merchant.values() for row in group), key=lambda row: row.date
        )
        shops = _count(count=len(names), noun="shop")
        by_card = all(
            row.source == "card_transaction" or row.transaction_type in CARD_PAYMENT_TYPES
            for row in matched
        )
        label = (
            f"Card payments at {shops}"
            if by_card
            else f"{_count(count=len(matched), noun='payment')} at {shops}"
        )
        return MerchantSpendingPayload(
            figure_chf=sum(totals.values(), Decimal(0)),
            source=_bookings_source(rows=matched, label=label),
            date_from=date_from,
            date_to=date_to,
            rows=[
                MerchantRow(
                    merchant=name,
                    amount_chf=totals[name],
                    share=round(float(totals[name] / largest), 3),
                    count=len(by_merchant[name]),
                )
                for name in names
            ],
        )

    async def _savings_goal(
        self, args: SavingsGoalArgs, token: str, today: date
    ) -> SavingsGoalPayload:
        accounts, customer, rows = await asyncio.gather(
            self._accounts(token=token),
            self.ledger.read(path="/customer", token=token),
            self._ledger_rows(token=token),
        )
        account = _account(accounts=accounts, account_id=args.account_id)
        goal_text = account["savings_goal"] or _customer_goal(
            goal=customer.get("savings_goal"), account=account
        )
        goal = None if goal_text is None else _amount_in(text=goal_text)
        if goal_text is None or goal is None:
            with_goal = [
                item["account_id"]
                for item in accounts
                if item["savings_goal"] is not None and _amount_in(text=item["savings_goal"])
            ]
            hint = (
                f"Accounts with a goal: {', '.join(with_goal)}."
                if with_goal
                else "No account has a goal; use account_balances instead."
            )
            raise TileError(f"{account['name']} ({args.account_id}) has no savings goal. {hint}")
        balance = _chf(amount=account["current_balance_chf"])
        month_start = today.replace(day=1)
        month_rows = [
            row
            for row in rows
            if row.source == "booking"
            and row.account_id == args.account_id
            and month_start <= row.date <= today
        ]
        month_name = MONTHS[today.month - 1]
        if not month_rows:
            label = f"No bookings in {month_name}"
        elif all(row.kind == "own_transfer" for row in month_rows):
            label = _count(count=len(month_rows), noun="transfer")
        else:
            label = f"{_count(count=len(month_rows), noun='booking')} in {month_name}"
        return SavingsGoalPayload(
            figure_chf=balance,
            source=_bookings_source(rows=month_rows, label=label),
            account_name=account["name"],
            goal_text=goal_text,
            goal_chf=goal,
            percent=float((balance / goal * 100).quantize(TENTH, rounding=ROUND_HALF_UP)),
            month_change_chf=sum((row.amount_chf for row in month_rows), Decimal(0)),
            month=_month(day=today),
        )

    async def _bill(self, args: BillArgs, token: str, today: date) -> BillPayload:
        upcoming = await self._upcoming(
            token=token, date_from=today, date_to=today + timedelta(days=BILL_LOOKAHEAD_DAYS)
        )
        payments = upcoming["items"]
        payment = next((item for item in payments if item["source_id"] == args.payment_id), None)
        if payment is None:
            listed = ", ".join(
                f"{item['source_id']} ({_payee(name=item['payee_name'])}, "
                f"{_day(day=date.fromisoformat(item['due_date']))})"
                for item in payments[:PAYEES_LISTED]
            )
            raise TileError(
                f"No upcoming payment {args.payment_id}. The next ones are: {listed or 'none'}."
            )
        row = _bill_row(payment=payment, balance_after=None)
        return BillPayload(
            figure_chf=row.amount_chf,
            source=_payments_source(
                payments=[payment], label=f"{row.payee}, due {_day(day=row.due)}"
            ),
            payee=row.payee,
            due=row.due,
            description=payment["description"],
            flag=row.flag,
        )

    async def _net_worth(self, args: NetWorthArgs, token: str, today: date) -> NetWorthPayload:
        overview = await self.ledger.read(path="/asset-overview", token=token)
        groups = {group["group"]: group for group in overview["groups"]}
        parts: list[WorthPart] = []
        items: list[dict[str, Any]] = []
        wanted: list[tuple[str, Literal["accounts", "securities", "pension"]]] = [
            ("accounts", "accounts"),
            ("investments", "securities"),
        ]
        if args.include_pension:
            wanted.append(("pension", "pension"))
        for name, part in wanted:
            group = groups.get(name)
            if group is None or not group["items"]:
                continue
            parts.append(
                WorthPart(
                    group=part, value_chf=_chf(amount=group["value_chf"]), count=len(group["items"])
                )
            )
            items += group["items"]
        if not parts:
            raise TileError("The customer has no accounts or securities to add up.")
        counts = {part.group: part.count for part in parts}
        label = _count(count=counts.get("accounts", 0), noun="account")
        if "securities" in counts:
            label += f" and {_count(count=counts['securities'], noun='depot')}"
        pension = groups.get("pension")
        if pension is not None and pension["items"]:
            label += ", with pillar 3a" if args.include_pension else ", without pillar 3a"
        return NetWorthPayload(
            figure_chf=sum((part.value_chf for part in parts), Decimal(0)),
            source=Source(
                label=label,
                kind="accounts",
                rows=[
                    SourceRow(
                        id=item["id"], text=item["name"], amount_chf=_chf(amount=item["value_chf"])
                    )
                    for item in items[:SOURCE_ROWS_MAX]
                ],
                count=len(items),
            ),
            parts=parts,
            includes_pension=args.include_pension,
        )

    async def _monthly_spending(
        self, args: MonthlySpendingArgs, token: str, today: date
    ) -> MonthlySpendingPayload:
        rows = await self._ledger_rows(token=token)
        if args.merchants is not None:
            _check_words(rows=[row for row in rows if row.kind == "spending"], words=args.merchants)
        date_from, date_to = _whole_months(months=args.months, today=today)
        sums = await self.ledger.sum_by_month(
            token=token,
            filters=Filters(
                kind=["spending"], text=args.merchants, date_from=date_from, date_to=date_to
            ),
            today=today,
        )
        months = [
            SpendingMonth(month=month.month, total_chf=-month.money_out_chf, count=month.count)
            for month in sums.months
        ]
        if sums.count == 0:
            raise TileError(
                f"No spending between {_day(day=date_from)} and {_day(day=date_to)}. "
                "Leave out merchants or choose more months."
            )
        highest = max(months, key=lambda month: month.total_chf)
        ids = {row_id for month_ids in sums.row_ids.values() for row_id in month_ids}
        return MonthlySpendingPayload(
            figure_chf=-sums.average_out_chf,
            source=_bookings_source(
                rows=[row for row in rows if row.id in ids],
                label=f"{_count(count=sums.count, noun='payment')}, {_months_text(months=months)}",
            ),
            months=months,
            highest=highest.month,
        )

    async def _income_and_spending(
        self, args: IncomeAndSpendingArgs, token: str, today: date
    ) -> IncomeAndSpendingPayload:
        rows = await self._ledger_rows(token=token)
        date_from, date_to = _whole_months(months=args.months, today=today)
        sums = await self.ledger.sum_by_month(
            token=token,
            filters=Filters(kind=["spending", "credit"], date_from=date_from, date_to=date_to),
            today=today,
        )
        if sums.count == 0:
            raise TileError(f"No bookings between {_day(day=date_from)} and {_day(day=date_to)}.")
        months = [
            CashflowMonth(
                month=month.month,
                income_chf=month.money_in_chf,
                spending_chf=-month.money_out_chf,
                left_chf=month.money_in_chf + month.money_out_chf,
            )
            for month in sums.months
        ]
        left = sum((month.left_chf for month in months), Decimal(0))
        ids = {row_id for month_ids in sums.row_ids.values() for row_id in month_ids}
        return IncomeAndSpendingPayload(
            figure_chf=(left / len(months)).quantize(CENT, rounding=ROUND_HALF_UP),
            source=_bookings_source(
                rows=[row for row in rows if row.id in ids],
                label=f"{_count(count=sums.count, noun='booking')}, {_months_text(months=months)}",
            ),
            months=months,
        )

    async def _securities(self, args: SecuritiesArgs, token: str, today: date) -> SecuritiesPayload:
        portfolio, positions = await asyncio.gather(
            self.ledger.read(path="/portfolio", token=token),
            self.ledger.read(path="/portfolio/positions", token=token),
        )
        items = positions["items"]
        if not items:
            raise TileError("The customer has no depot, so there are no securities to show.")
        invested = _chf(amount=portfolio["invested_chf"])
        noun = "ETF" if all("ETF" in item["name"] for item in items) else "position"
        return SecuritiesPayload(
            figure_chf=_chf(amount=portfolio["total_value_chf"]),
            source=Source(
                label=f"{_count(count=len(items), noun=noun)}, "
                f"CHF {_text(amount=invested)} paid in",
                kind="positions",
                rows=[
                    SourceRow(
                        id=item["isin"],
                        date=item["price_date"],
                        text=item["name"],
                        amount_chf=_chf(amount=item["market_value_chf"]),
                    )
                    for item in items[:SOURCE_ROWS_MAX]
                ],
                count=len(items),
            ),
            invested_chf=invested,
            allocation=[
                AllocationPart(
                    label=ASSET_CLASSES.get(part["label"]) or part["label"],
                    value_chf=_chf(amount=part["value_chf"]),
                    weight_pct=part["weight_pct"],
                )
                for part in portfolio["allocation"]["asset_class"]
            ],
            positions=len(items),
        )

    async def _regular_payments(
        self, args: RegularPaymentsArgs, token: str, today: date
    ) -> RegularPaymentsPayload:
        upcoming = await self._upcoming(
            token=token, date_from=today, date_to=today + timedelta(days=REGULAR_LOOKAHEAD_DAYS)
        )
        payments = upcoming["items"]
        recurring = None
        rows: list[RegularPaymentRow] = []
        source_rows: list[SourceRow] = []
        for payee in args.payees:
            words = re.compile(rf"\b{re.escape(payee)}", re.IGNORECASE)
            payment = next((item for item in payments if words.search(item["payee_name"])), None)
            if payment is not None:
                rows.append(
                    RegularPaymentRow(
                        payee=payee,
                        amount_chf=_chf(amount=payment["amount_chf"]),
                        next_due=payment["due_date"],
                    )
                )
                source_rows.append(_payment_source_row(payment=payment))
                continue
            # A card subscription has no upcoming payment; its rhythm is in the bookings.
            if recurring is None:
                recurring = await self.recurring.list_recurring(token=token, today=today)
            known = next(
                (
                    item
                    for item in recurring.recurring
                    if item.active and words.search(item.payee) is not None
                ),
                None,
            )
            if known is None:
                listed = ", ".join(
                    dict.fromkeys(_payee(name=item["payee_name"]) for item in payments)
                )
                raise TileError(
                    f"No regular payment to {payee}. The upcoming payees are: {listed}. "
                    "Send the call again without it."
                )
            rows.append(
                RegularPaymentRow(
                    payee=payee, amount_chf=known.last_paid_chf, next_due=known.next_expected
                )
            )
            source_rows.append(
                SourceRow(
                    id=known.ids[-1],
                    date=known.last_date,
                    text=known.payee,
                    amount_chf=-known.last_paid_chf,
                )
            )
        due_months = {row.next_due.strftime("%Y-%m") for row in rows}
        label = (
            f"{_count(count=len(rows), noun='payment')} in {MONTHS[rows[0].next_due.month - 1]}"
            if len(due_months) == 1
            else _count(count=len(rows), noun="upcoming payment")
        )
        return RegularPaymentsPayload(
            figure_chf=sum((row.amount_chf for row in rows), Decimal(0)),
            source=Source(label=label, kind="payments", rows=source_rows, count=len(source_rows)),
            rows=rows,
        )

    async def _pillar_3a(self, args: Pillar3aArgs, token: str, today: date) -> Pillar3aPayload:
        accounts, rows = await asyncio.gather(
            self._accounts(token=token), self._ledger_rows(token=token)
        )
        pillar = next((item for item in accounts if item["type"] == "pillar3a"), None)
        if pillar is None:
            raise TileError("The customer has no pillar 3a account at this bank.")
        year = today.year
        maximum = _maximum_3a(purpose=pillar["purpose"] or "", year=year)
        paid_rows = [
            row
            for row in rows
            if row.source == "booking"
            and row.account_id == pillar["account_id"]
            and row.amount_chf > 0
            and row.transaction_type != "interest"
            and row.date.year == year
            and row.date <= today
        ]
        paid = sum((row.amount_chf for row in paid_rows), Decimal(0))
        upcoming = await self._upcoming(token=token, date_from=today, date_to=date(year, 12, 31))
        to_pillar = [item for item in upcoming["items"] if item["payee_name"] == pillar["name"]]
        standing = sum(
            (
                _chf(amount=item["amount_chf"])
                for item in to_pillar
                if item["type"] == "standing_order"
            ),
            Decimal(0),
        )
        planned = [item for item in to_pillar if item["type"] != "standing_order"]
        source = (
            _payments_source(
                payments=planned, label=_count(count=len(planned), noun="planned transfer")
            )
            if planned
            else _bookings_source(
                rows=paid_rows, label=f"{_count(count=len(paid_rows), noun='payment')} in {year}"
            )
        )
        return Pillar3aPayload(
            figure_chf=maximum - paid - standing,
            source=source,
            year=year,
            maximum_chf=maximum,
            paid_chf=paid,
            standing_orders_chf=standing,
            balance_chf=_chf(amount=pillar["current_balance_chf"]),
            planned=[
                PlannedTransfer(
                    id=item["source_id"],
                    date=item["due_date"],
                    amount_chf=_chf(amount=item["amount_chf"]),
                )
                for item in planned
            ],
        )

    async def _account_balances(
        self, args: AccountBalancesArgs, token: str, today: date
    ) -> AccountBalancesPayload:
        accounts = await self._accounts(token=token)
        chosen = [
            _account(accounts=accounts, account_id=account_id)
            for account_id in dict.fromkeys(args.account_ids)
        ]
        rows = [
            AccountRow(
                account_id=account["account_id"],
                name=account["name"],
                balance_chf=_chf(amount=account["current_balance_chf"]),
                purpose=account["purpose"],
            )
            for account in chosen
        ]
        noun = "savings account" if all(item["type"] == "savings" for item in chosen) else "account"
        return AccountBalancesPayload(
            figure_chf=sum((row.balance_chf for row in rows), Decimal(0)),
            source=Source(
                label=_count(count=len(rows), noun=noun),
                kind="accounts",
                rows=[
                    SourceRow(id=row.account_id, text=row.name, amount_chf=row.balance_chf)
                    for row in rows
                ],
                count=len(rows),
            ),
            rows=rows,
        )

    async def _mortgage(self, args: MortgageArgs, token: str, today: date) -> MortgagePayload:
        loans = await self.ledger.read(path="/loans", token=token)
        items = loans["items"]
        if not items:
            raise TileError("The customer has no mortgage or loan at this bank.")
        tranches = [
            Tranche(
                loan_id=item["loan_id"],
                product=item["product"],
                balance_chf=_chf(amount=item["balance"]),
                interest_rate=item["interest_rate"],
                maturity_date=item["maturity_date"],
                next_interest_date=item["next_interest_date"],
            )
            for item in items
        ]
        soon = [
            tranche
            for tranche in tranches
            if tranche.maturity_date is not None
            and today <= tranche.maturity_date <= today + timedelta(days=MATURITY_SOON_DAYS)
        ]
        return MortgagePayload(
            figure_chf=_chf(amount=loans["total_balance_chf"]),
            source=Source(
                label=_count(count=len(tranches), noun="tranche"),
                kind="loans",
                rows=[
                    SourceRow(
                        id=tranche.loan_id,
                        date=tranche.maturity_date,
                        text=tranche.product,
                        amount_chf=tranche.balance_chf,
                    )
                    for tranche in tranches
                ],
                count=len(tranches),
            ),
            annual_interest_chf=_chf(amount=loans["annual_interest_chf"]),
            tranches=tranches,
            next_maturity=min(
                soon, key=lambda tranche: tranche.maturity_date or today, default=None
            ),
        )

    async def _card_bill(self, args: CardBillArgs, token: str, today: date) -> CardBillPayload:
        cards = (await self.ledger.read(path="/cards", token=token))["items"]
        card = next((item for item in cards if item["card_id"] == args.card_id), None)
        credit = [item["card_id"] for item in cards if item["type"] == "credit"]
        credit_hint = (
            f"The credit cards are: {', '.join(credit)}."
            if credit
            else "The customer has no credit card."
        )
        if card is None:
            raise TileError(f"No card {args.card_id}. {credit_hint}")
        if card["type"] != "credit":
            raise TileError(
                f"{args.card_id} is a debit card; its payments are bookings already. {credit_hint}"
            )
        card_path = f"/cards/{quote(args.card_id, safe='')}"
        statements = (await self.ledger.read(path=f"{card_path}/statements", token=token))["items"]
        unpaid = sorted(
            (item for item in statements if item["status"] != "settled"),
            key=lambda item: item["period_from"],
        )
        if not unpaid:
            raise TileError(f"Nothing is due on the {card['product']}: every statement is paid.")
        statement = unpaid[0]
        purchases = await self.ledger.read(
            path=f"{card_path}/transactions",
            token=token,
            params={"statement": statement["statement_id"], "limit": SOURCE_ROWS_MAX},
        )
        period = statement["period_from"][:7]
        return CardBillPayload(
            figure_chf=_chf(amount=statement["total_chf"]),
            source=Source(
                label=f"{_count(count=purchases['total'], noun='purchase')} in "
                f"{_month_name(month=period)}",
                kind="bookings",
                rows=[
                    SourceRow(
                        id=item["card_transaction_id"],
                        date=item["transaction_date"],
                        text=item["merchant_name"] or item["merchant_text"],
                        amount_chf=-_chf(amount=item["amount_chf"]),
                    )
                    for item in purchases["items"]
                ],
                count=purchases["total"],
            ),
            card_name=card["product"],
            period=period,
            due=statement["debit_date"],
            flag="provisional" if statement["status"] == "open" else None,
            purchases=statement["transactions_count"],
        )

    async def _ledger_rows(self, token: str) -> list[LedgerRow]:
        if token not in self._rows:
            self._rows[token] = asyncio.ensure_future(self.ledger.list_rows(token=token))
        return await self._rows[token]

    async def _accounts(self, token: str) -> list[dict[str, Any]]:
        return (await self.ledger.read(path="/accounts", token=token))["items"]

    async def _upcoming(
        self, token: str, date_from: date, date_to: date, account_id: str | None = None
    ) -> dict[str, Any]:
        params = {"from": date_from.isoformat(), "to": date_to.isoformat()}
        if account_id is not None:
            params["account"] = account_id
        return await self.ledger.read(path="/upcoming-payments", token=token, params=params)

    async def _balance_preview(self, token: str, account_id: str, date_to: date) -> dict[str, Any]:
        return await self.ledger.read(
            path=f"/accounts/{quote(account_id, safe='')}/balance-preview",
            token=token,
            params={"to": date_to.isoformat()},
        )


def _args_message(template: str, error: ValidationError) -> str:
    messages = []
    for item in error.errors():
        name = ".".join(str(part) for part in item["loc"]) or "arguments"
        match item["type"]:
            case "extra_forbidden":
                messages.append(f"{template} has no argument {name}. Send it again without it.")
            case "missing":
                messages.append(f"{template} needs the argument {name}.")
            case _:
                messages.append(f"{name}: {item['msg']}.")
    allowed = ", ".join(TEMPLATES[template][0].model_fields) or "none"
    return f"{' '.join(messages)} The arguments of {template} are: {allowed}."


def _account(accounts: list[dict[str, Any]], account_id: str) -> dict[str, Any]:
    account = next((item for item in accounts if item["account_id"] == account_id), None)
    if account is None:
        listed = ", ".join(f"{item['account_id']} ({item['name']})" for item in accounts)
        raise TileError(f"No account {account_id}. The accounts are {listed}.")
    return account


def _payday(rows: list[LedgerRow], account_id: str, today: date) -> date:
    salaries = [row for row in rows if row.source == "booking" and row.transaction_type == "salary"]
    if not salaries:
        raise TileError("No salary in the bookings, so there is no payday. Use due_soon instead.")
    on_account = [row for row in salaries if row.account_id == account_id]
    if not on_account:
        accounts = ", ".join(sorted({row.account_id for row in salaries}))
        raise TileError(f"No salary arrives on {account_id}. The salary arrives on {accounts}.")
    last = on_account[-1].date
    if (today - last).days > SALARY_STALE_DAYS:
        raise TileError(
            f"The last salary arrived on {_day(day=last)}{last.year}, so no next payday can be "
            "expected. Use due_soon instead."
        )
    usual_day = Counter(row.date.day for row in on_account[-SALARY_RHYTHM_PAYMENTS:]).most_common(
        1
    )[0][0]
    year, month = (last.year + 1, 1) if last.month == 12 else (last.year, last.month + 1)
    payday = date(year, month, min(usual_day, calendar.monthrange(year, month)[1]))
    # The salary comes on its usual day, or the working day before when that day is a weekend or a
    # holiday: the 25th, but 24.12.2026 because the 25th is Christmas, so 23.12. is the day before.
    while payday.weekday() >= 5 or (payday.month, payday.day) in FIXED_HOLIDAYS:
        payday -= timedelta(days=1)
    if payday <= today:
        raise TileError(
            f"The salary expected on {_day(day=payday)} has not arrived yet, so the next payday "
            "is unknown. Use due_soon instead."
        )
    return payday


def _income(rows: list[LedgerRow], counterparty: str, today: date) -> Income:
    received = [
        row
        for row in rows
        if row.source == "booking"
        and row.amount_chf > 0
        and _has_words(row=row, words=[counterparty])
    ]
    if not received:
        raise TileError(
            f"No money came from {counterparty}. Regular income comes from: "
            f"{', '.join(_regular_payers(rows=rows, today=today)) or 'nobody'}."
        )
    by_month: dict[str, list[LedgerRow]] = defaultdict(list)
    for row in received:
        by_month[_month(day=row.date)].append(row)
    current = _month(day=today)
    history = [month for month in sorted(by_month) if month < current][-INCOME_HISTORY_MONTHS:]
    if len(history) < INCOME_MIN_MONTHS:
        raise TileError(
            f"{counterparty} paid in {len(history)} months only, too few to expect a next payment."
        )
    usual_day = statistics.median_low([_main(rows=by_month[month]).date.day for month in history])
    amount = statistics.median_low(
        [sum((row.amount_chf for row in by_month[month]), Decimal(0)) for month in history]
    )
    months = []
    window_rows: list[LedgerRow] = []
    for month in [_shift(month=current, by=back) for back in range(1 - INCOME_WINDOW_MONTHS, 1)]:
        arrivals = by_month.get(month, [])
        window_rows += arrivals
        if not arrivals:
            months.append(IncomeMonth(month=month, arrived_on=None, amount_chf=None, state="open"))
            continue
        first = _main(rows=arrivals).date
        months.append(
            IncomeMonth(
                month=month,
                arrived_on=first,
                amount_chf=sum((row.amount_chf for row in arrivals), Decimal(0)),
                state="late" if first.day > usual_day + LATE_AFTER_DAYS else "on_time",
            )
        )
    return Income(
        usual_day=usual_day,
        amount=amount,
        months=months,
        status="arrived" if by_month.get(current) else "not_arrived",
        rows=window_rows,
    )


def _main(rows: list[LedgerRow]) -> LedgerRow:
    # The largest payment of a month is the income; a small refund from the same payer is not.
    return max(rows, key=lambda row: row.amount_chf)


def _regular_payers(rows: list[LedgerRow], today: date) -> list[str]:
    since = today - timedelta(days=365)
    months: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if row.kind == "credit" and row.date >= since and row.counterparty is not None:
            months[row.counterparty].add(_month(day=row.date))
    return [name for name, seen in months.items() if len(seen) >= INCOME_MIN_MONTHS]


def _check_words(rows: list[LedgerRow], words: list[str]) -> None:
    for word in words:
        if not any(_has_words(row=row, words=[word]) for row in rows):
            raise TileError(
                f"No payment mentions {word}. Check the spelling, or send the call without it."
            )


def _period(period: str, today: date) -> tuple[date, date]:
    month_start = today.replace(day=1)
    if period == "this_month":
        return month_start, today
    last_month_end = month_start - timedelta(days=1)
    if period == "last_month":
        return last_month_end.replace(day=1), last_month_end
    return _whole_months(months=3, today=today)


def _whole_months(months: int, today: date) -> tuple[date, date]:
    first = date.fromisoformat(f"{_shift(month=_month(day=today), by=-months)}-01")
    return first, today.replace(day=1) - timedelta(days=1)


def _customer_goal(goal: str | None, account: dict[str, Any]) -> str | None:
    # The customer's own goal belongs to a savings account whose name or purpose shares a word.
    if goal is None or account["type"] != "savings":
        return None
    words = re.findall(r"\w{5,}", f"{account['name']} {account['purpose'] or ''}")
    return goal if any(word.casefold() in goal.casefold() for word in words) else None


def _amount_in(text: str) -> Decimal | None:
    match = AMOUNT.search(text)
    return None if match is None else Decimal(re.sub(r"['’]", "", match[1]))


def _maximum_3a(purpose: str, year: int) -> Decimal:
    match = re.search(rf"{year}\D{{0,3}}{AMOUNT.pattern}", purpose)
    if match is not None:
        return Decimal(re.sub(r"['’]", "", match[1]))
    if year not in PILLAR_3A_LIMITS_CHF:
        raise TileError(f"The pillar 3a maximum for {year} is not known yet.")
    return PILLAR_3A_LIMITS_CHF[year]


def _bill_row(payment: dict[str, Any], balance_after: Decimal | None) -> BillRow:
    description = payment["description"] or ""
    if payment["type"] == "card_statement":
        payee, _, rest = payment["payee_name"].partition(" Abrechnung")
        month = next((word for word in rest.split() if word in GERMAN_MONTHS), None)
        detail = None if month is None else GERMAN_MONTHS[month]
    else:
        payee, detail = _payee(name=payment["payee_name"]), _detail(description=description)
    return BillRow(
        id=payment["source_id"],
        due=payment["due_date"],
        payee=payee,
        detail=detail,
        amount_chf=_chf(amount=payment["amount_chf"]),
        balance_after_chf=balance_after,
        flag=_flag(description=description),
    )


def _payee(name: str) -> str:
    name = name.split(", ")[0]
    name = re.sub(r"\s*\(.*?\)", "", name)
    return LEGAL_SUFFIX.sub("", name) or name


def _detail(description: str) -> str | None:
    for pattern, english in DETAILS:
        match = pattern.search(description)
        if match is not None:
            return english(match)
    words = [
        word
        for word in re.sub(r"\(.*?\)", "", description).split()
        if word not in GERMAN_MONTHS and re.fullmatch(r"[\d.,/–-]+", word) is None
    ]
    return " ".join(words[:4]) or None


def _flag(description: str) -> Flag | None:
    if re.search(r"Mahnung", description, re.IGNORECASE):
        return "reminder"
    if re.search(r"vorläufig|provisorisch", description, re.IGNORECASE):
        return "provisional"
    return None


def _payment_source_row(payment: dict[str, Any]) -> SourceRow:
    return SourceRow(
        id=payment["source_id"],
        date=payment["due_date"],
        text=f"{payment['payee_name']}: {payment['description']}",
        amount_chf=-_chf(amount=payment["amount_chf"]),
    )


def _payments_source(payments: list[dict[str, Any]], label: str) -> Source:
    return Source(
        label=label,
        kind="payments",
        rows=[_payment_source_row(payment=payment) for payment in payments[:SOURCE_ROWS_MAX]],
        count=len(payments),
    )


def _bookings_source(rows: list[LedgerRow], label: str) -> Source:
    return Source(
        label=label,
        kind="bookings",
        rows=[
            SourceRow(id=row.id, date=row.date, text=row.text, amount_chf=row.amount_chf)
            for row in rows[:SOURCE_ROWS_MAX]
        ],
        count=len(rows),
    )


def _per_day(amount: Decimal, days: int) -> Decimal:
    return (amount / days).quantize(CENT, rounding=ROUND_HALF_UP)


def _merchant_title(payload: MerchantSpendingPayload) -> str:
    first, last = MONTHS[payload.date_from.month - 1], MONTHS[payload.date_to.month - 1]
    when = f"in {first}" if first == last else f"since {first}"
    name = payload.rows[0].merchant if len(payload.rows) == 1 else "Shops"
    titled = f"{name} {when}"
    return titled if len(titled) <= 28 else f"Shops {when}"


def _months_text(months: list[Any]) -> str:
    first, last = months[0].month, months[-1].month
    if first[:4] != last[:4]:
        return f"{_month_name(month=first)} {first[:4]} to {_month_name(month=last)} {last[:4]}"
    return f"{_month_name(month=first)} to {_month_name(month=last)}"


def _month_name(month: str) -> str:
    return MONTHS[int(month[5:7]) - 1]


def _day(day: date) -> str:
    return f"{day.day:02d}.{day.month:02d}."


def _text(amount: Decimal) -> str:
    return f"{amount:,.2f}".replace(",", "'")


def _count(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"
