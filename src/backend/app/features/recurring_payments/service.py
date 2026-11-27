import calendar
import re
import statistics
from collections import defaultdict
from datetime import date
from decimal import Decimal

from app.clients.banking import BankingClient
from app.features.ledger.schemas import LedgerRow
from app.features.ledger.service import LedgerService
from app.features.recurring_payments.schemas import (
    Cadence,
    InstalmentPlan,
    PriceChange,
    RecurringPayment,
    RecurringPayments,
)

# Median gap in days that makes a cadence, and the months between two payments.
CADENCES: dict[Cadence, tuple[int, int, int]] = {
    "monthly": (26, 35, 1),
    "quarterly": (80, 100, 3),
    "yearly": (350, 380, 12),
}
MIN_PAYMENTS = 3
BILL_TYPES = {"ebill", "qr_bill", "direct_debit", "standing_order", "domestic", "international"}
# Swiss banks write the instalment into the booking text, such as "Ratenvertrag RW-1, Rate 20/24".
INSTALMENT = re.compile(r"Rate (\d+)/(\d+)")


class RecurringPaymentService:
    def __init__(self, ledger: LedgerService, banking: BankingClient) -> None:
        self.ledger = ledger
        self.banking = banking

    async def list_recurring(self, token: str) -> RecurringPayments:
        """Payments that come back every month, quarter or year, and instalment plans."""
        info = await self.banking.get(path="/system/info")
        today = date.fromisoformat(info["today"])
        rows = await self.ledger.list_rows(token=token)

        by_plan: dict[tuple[str, str], list[tuple[LedgerRow, re.Match[str]]]] = defaultdict(list)
        by_payee: dict[str, list[LedgerRow]] = defaultdict(list)
        for row in rows:
            if row.kind != "spending":
                continue
            match = INSTALMENT.search(row.text)
            if match is None:
                by_payee[_payee(row=row)].append(row)
                continue
            plan = row.text[: match.start()].rstrip(" ,")
            by_plan[(_payee(row=row), plan)].append((row, match))

        recurring = [
            payment
            for payee, payments in by_payee.items()
            if (payment := _recurring(payee=payee, rows=payments, today=today)) is not None
        ]
        plans = [
            _plan(payee=payee, plan=plan, rows=items) for (payee, plan), items in by_plan.items()
        ]
        return RecurringPayments(
            recurring=sorted(recurring, key=lambda payment: -payment.paid_per_year_chf),
            instalment_plans=sorted(plans, key=lambda plan: plan.last_date, reverse=True),
        )


def _recurring(payee: str, rows: list[LedgerRow], today: date) -> RecurringPayment | None:
    if len(rows) < MIN_PAYMENTS:
        return None
    gaps = [(after.date - before.date).days for before, after in zip(rows, rows[1:], strict=False)]
    median_gap = statistics.median(gaps)
    cadence = _cadence(gaps=gaps, median_gap=median_gap)
    if cadence is None:
        return None
    last = rows[-1]
    last_paid = -last.amount_chf
    months = CADENCES[cadence][2]
    return RecurringPayment(
        payee=payee,
        cadence=cadence,
        payments=len(rows),
        last_date=last.date,
        last_paid_chf=last_paid,
        paid_per_year_chf=last_paid * (12 // months),
        next_expected=_months_later(day=last.date, months=months),
        active=(today - last.date).days <= median_gap * 1.5,
        price_changes=_price_changes(rows=rows, cadence=cadence),
        ids=[row.id for row in rows],
    )


def _cadence(gaps: list[int], median_gap: float) -> Cadence | None:
    for cadence, (shortest, longest, _) in CADENCES.items():
        if not shortest <= median_gap <= longest:
            continue
        # Two thirds of the gaps fit, so one skipped or doubled month still counts.
        regular = sum(shortest <= gap <= longest for gap in gaps)
        return cadence if regular * 3 >= len(gaps) * 2 else None
    return None


def _price_changes(rows: list[LedgerRow], cadence: Cadence) -> list[PriceChange]:
    prices = [_price(row=row) for row in rows]
    if cadence == "yearly":
        # A shop visited every December has no price; only a bill does.
        if any(row.transaction_type not in BILL_TYPES for row in rows):
            return []
    else:
        runs = 1 + sum(price != before for before, price in zip(prices, prices[1:], strict=False))
        # ponytail: a bill whose amount changes in most periods (electricity) has no price to rise.
        if runs * 3 > len(prices):
            return []
    changes: list[PriceChange] = []
    in_force = 0  # the last payment at the price that holds
    for index in range(1, len(rows)):
        if prices[index] == prices[in_force]:
            in_force = index
            continue
        # A price holds when one of the next two payments repeats it or none follows. A one-off
        # amount between regular ones, such as a final tax bill, is no new price.
        following = prices[index + 1 : index + 3]
        if cadence != "yearly" and following and prices[index] not in following:
            continue
        changes.append(
            PriceChange(
                date=rows[index].date,
                old_price=prices[in_force][0],
                new_price=prices[index][0],
                currency=prices[index][1],
                id_before=rows[in_force].id,
                id_after=rows[index].id,
            )
        )
        in_force = index
    return changes


def _price(row: LedgerRow) -> tuple[Decimal, str]:
    # In the original currency, so a USD subscription doesn't rise when only the rate moved.
    if row.original_amount is None or row.original_currency is None:
        return (-row.amount_chf, "CHF")
    return (-row.original_amount, row.original_currency)


def _plan(payee: str, plan: str, rows: list[tuple[LedgerRow, re.Match[str]]]) -> InstalmentPlan:
    last, match = max(rows, key=lambda item: (int(item[1][1]), item[0].date))
    paid, total = int(match[1]), int(match[2])
    left = max(total - paid, 0)
    instalment = -last.amount_chf
    return InstalmentPlan(
        payee=payee,
        plan=plan,
        instalment_chf=instalment,
        paid=paid,
        total=total,
        left=left,
        left_chf=instalment * left,
        last_date=last.date,
        ids=[row.id for row, _ in rows],
    )


def _months_later(day: date, months: int) -> date:
    # The same day of the month, or the month's last day when it is shorter.
    year, month = divmod(day.month - 1 + months, 12)
    year, month = day.year + year, month + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def _payee(row: LedgerRow) -> str:
    return row.text if row.counterparty is None else row.counterparty
