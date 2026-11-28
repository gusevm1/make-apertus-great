"""What a tile's figures mean, in the server's words: the verdict is computed, never the model's."""

import re
from datetime import date
from decimal import Decimal

from app.features.tiles.schemas import (
    AccountBalancesPayload,
    AnyPayload,
    BillPayload,
    BillRow,
    BillsUntilPaydayPayload,
    CardBillPayload,
    DueSoonPayload,
    ExpectedIncomePayload,
    IncomeAndSpendingPayload,
    MerchantSpendingPayload,
    MonthlySpendingPayload,
    MortgagePayload,
    NetWorthPayload,
    PaydayBalancePayload,
    Pillar3aPayload,
    RegularPaymentsPayload,
    SavingsGoalPayload,
    SecuritiesPayload,
)

# ponytail: fixed CHF per remaining day; scale with the customer's usual spending if it misleads
ONLY_JUST_PER_DAY = Decimal(20)
COMFORTABLY_PER_DAY = Decimal(60)
MONTHS = "January February March April May June July August September October November December"
MONTH_NAMES = MONTHS.split()
DOUBLE_DOT = re.compile(r"\.\.(?=\s|$)")
GROUPS = {"accounts": "accounts", "securities": "securities", "pension": "pillar 3a"}


def meaning(payload: AnyPayload, today: date) -> str:
    """One or two plain sentences: what the figures say, with the verdict where there is one."""
    # A day such as 23.12. ends its sentence with its own dot.
    return DOUBLE_DOT.sub(".", _meaning(payload=payload, today=today))


def _meaning(payload: AnyPayload, today: date) -> str:
    match payload:
        case PaydayBalancePayload():
            return _payday(payload=payload)
        case BillsUntilPaydayPayload():
            return _bills_until_payday(payload=payload, today=today)
        case DueSoonPayload():
            first = payload.rows[0] if payload.rows else None
            text = (
                f"{_count(count=payload.count, noun='payment')} of together "
                f"{_chf(amount=payload.figure_chf)} fall due in the next {payload.days} days."
            )
            reminders = [row for row in payload.rows if row.flag == "reminder"]
            if reminders:
                return f"{text} {_reminder(row=reminders[0], today=today)}"
            if first is None:
                return text
            return f"{text} The first is {_row(row=first)}."
        case ExpectedIncomePayload():
            return _expected_income(payload=payload)
        case MerchantSpendingPayload():
            shops = ", ".join(
                f"{row.merchant} {_chf(amount=row.amount_chf)}" for row in payload.rows
            )
            return (
                f"From {_day(day=payload.date_from)} to {_day(day=payload.date_to)}, "
                f"{_chf(amount=payload.figure_chf)} went to these shops: {shops}."
            )
        case SavingsGoalPayload():
            return _savings_goal(payload=payload)
        case BillPayload():
            text = (
                f"{_chf(amount=payload.figure_chf)} to {payload.payee} fall due on "
                f"{_day(day=payload.due)}, {_in_days(day=payload.due, today=today)}."
            )
            if payload.flag == "reminder":
                return f"{text} This is a reminder: it cannot wait."
            return text
        case NetWorthPayload():
            parts = ", ".join(
                f"{GROUPS[part.group]} {_chf(amount=part.value_chf)}" for part in payload.parts
            )
            return f"Together the customer owns {_chf(amount=payload.figure_chf)}: {parts}."
        case MonthlySpendingPayload():
            highest = next(item for item in payload.months if item.month == payload.highest)
            return (
                f"Over {len(payload.months)} whole months, on average "
                f"{_chf(amount=payload.figure_chf)} went out per month. The highest month was "
                f"{_month(month=highest.month)} with {_chf(amount=highest.total_chf)}."
            )
        case IncomeAndSpendingPayload():
            short = [item for item in payload.months if item.left_chf < 0]
            text = (
                f"Over {len(payload.months)} months, on average "
                f"{_chf(amount=payload.figure_chf)} per month were left after spending."
            )
            if not short:
                return f"{text} No month spent more than came in."
            return (
                f"{text} {_count(count=len(short), noun='month')} spent more than came in, "
                f"such as {_month(month=short[-1].month)}."
            )
        case SecuritiesPayload():
            largest = max(payload.allocation, key=lambda part: part.weight_pct, default=None)
            text = (
                f"The depot is worth {_chf(amount=payload.figure_chf)} in "
                f"{_count(count=payload.positions, noun='position')}"
            )
            if largest is None:
                return f"{text}."
            return f"{text}; the largest part is {largest.label} at {largest.weight_pct:.1f} %."
        case RegularPaymentsPayload():
            payees = ", ".join(
                f"{row.payee} {_chf(amount=row.amount_chf)} on {_day(day=row.next_due)}"
                for row in payload.rows
            )
            return (
                f"One round of these regular payments costs {_chf(amount=payload.figure_chf)}: "
                f"{payees}."
            )
        case Pillar3aPayload():
            return _pillar_3a(payload=payload)
        case AccountBalancesPayload():
            accounts = ", ".join(
                f"{row.name} {_chf(amount=row.balance_chf)}" for row in payload.rows
            )
            return f"Together {_chf(amount=payload.figure_chf)}: {accounts}."
        case MortgagePayload():
            text = (
                f"The mortgage is {_chf(amount=payload.figure_chf)} in "
                f"{_count(count=len(payload.tranches), noun='tranche')}, with "
                f"{_chf(amount=payload.annual_interest_chf)} interest a year."
            )
            soon = payload.next_maturity
            if soon is None or soon.maturity_date is None:
                return f"{text} No tranche runs out in the next 18 months."
            return (
                f"{text} The {soon.product} of {_chf(amount=soon.balance_chf)} at "
                f"{soon.interest_rate:.2f} % runs out on {_date(day=soon.maturity_date)}, so it "
                "needs a decision before then."
            )
        case CardBillPayload():
            due = "" if payload.due is None else f", debited on {_day(day=payload.due)}"
            text = (
                f"The {payload.card_name} statement for {_month(month=payload.period)} is "
                f"{_chf(amount=payload.figure_chf)} for "
                f"{_count(count=payload.purchases, noun='purchase')}{due}."
            )
            if payload.flag == "provisional":
                return f"{text} The month is still open, so it can still grow."
            return text


# The first words of the payday meaning answer "Does my money last?": the verdict's polarity.
def _payday(payload: PaydayBalancePayload) -> str:
    left, per_day, days = payload.figure_chf, payload.per_day_chf, payload.days
    after = (
        f"after the {_count(count=payload.upcoming_count, noun='payment')} that are due before "
        f"the next salary on {_day(day=payload.payday)}, {_chf(amount=left)} are left on "
        f"{_day(day=payload.day_before)}"
    )
    if left < 0:
        text = f"No. The money does not last: {after}, so {_chf(amount=-left)} are missing."
    elif per_day < ONLY_JUST_PER_DAY:
        text = (
            f"Yes, but only just. The money lasts: {after}. That is {_chf(amount=per_day)} a day "
            f"for {days} days."
        )
    elif per_day < COMFORTABLY_PER_DAY:
        text = f"Yes. The money lasts: {after}. That is {_chf(amount=per_day)} a day for {days} days."
    else:
        text = (
            f"Yes, comfortably. The money lasts: {after}. That is {_chf(amount=per_day)} a day for "
            f"{days} days."
        )
    other = payload.alternative
    if other is None:
        return text
    name = (
        f"the income from {other.counterparty}"
        if other.label is None
        else f"{other.label} from {other.counterparty}"
    )
    return (
        f"{text} The second case: {name} ({_chf(amount=other.amount_chf)}) has not arrived this "
        f"month and is not counted above; if it arrives, {_chf(amount=other.left_chf)} are left "
        f"on {_day(day=payload.day_before)}."
    )


def _bills_until_payday(payload: BillsUntilPaydayPayload, today: date) -> str:
    text = (
        f"{_count(count=len(payload.rows), noun='payment')} of together "
        f"{_chf(amount=payload.figure_chf)} fall due before the salary on "
        f"{_day(day=payload.payday)}."
    )
    last = payload.rows[-1].balance_after_chf
    if last is not None:
        text += f" After the last one, {_chf(amount=last)} are left."
    reminders = [row for row in payload.rows if row.flag == "reminder"]
    if reminders:
        text += f" {_reminder(row=reminders[0], today=today)}"
    others = [row for row in payload.rows if row not in reminders[:1]]
    if not others:
        return text
    order = "; ".join(_row(row=row) for row in others)
    last = " and ".join(_row(row=row) for row in reversed(others[-2:]))
    return (
        f"{text} The {'others' if reminders else 'payments'} fall due in this order: {order}. "
        f"Last to fall due: {last}. Only a payee can agree to a later date."
    )


def _expected_income(payload: ExpectedIncomePayload) -> str:
    current = payload.months[-1]
    usual = f"It usually arrives around the {_ordinal(day=payload.usual_day)} of the month."
    late = [item for item in payload.months[:-1] if item.state == "late" and item.arrived_on]
    last_late = (
        ""
        if not late or late[-1].arrived_on is None
        else f" Last time it came late, on {_day(day=late[-1].arrived_on)}."
    )
    if payload.status == "arrived" and current.arrived_on is not None:
        return (
            f"The income from {payload.counterparty} ({_chf(amount=payload.figure_chf)}) arrived "
            f"this month on {_day(day=current.arrived_on)}. {usual}{last_late}"
        )
    return (
        f"The income from {payload.counterparty} ({_chf(amount=payload.figure_chf)}) has not "
        f"arrived this month. {usual}{last_late}"
    )


def _savings_goal(payload: SavingsGoalPayload) -> str:
    if payload.percent >= 100:
        text = (
            f"{payload.account_name} holds {_chf(amount=payload.figure_chf)}, already above its "
            f"goal of {_chf(amount=payload.goal_chf)}"
        )
    else:
        text = (
            f"{payload.account_name} holds {_chf(amount=payload.figure_chf)}, which is "
            f"{payload.percent:.1f} % of the goal of {_chf(amount=payload.goal_chf)}"
        )
    month = _month(month=payload.month)
    change = payload.month_change_chf
    if change < 0:
        return f"{text}; {_chf(amount=-change)} went out of it in {month}."
    if change > 0:
        return f"{text}; {_chf(amount=change)} came in in {month}."
    return f"{text}; nothing came in or went out in {month}."


def _pillar_3a(payload: Pillar3aPayload) -> str:
    text = (
        f"{_chf(amount=payload.paid_chf)} went into pillar 3a in {payload.year} so far, of the "
        f"maximum of {_chf(amount=payload.maximum_chf)}"
    )
    if payload.standing_orders_chf > 0:
        text += f", and standing orders still pay in {_chf(amount=payload.standing_orders_chf)}"
    missing = payload.figure_chf
    if missing <= 0:
        return f"{text}. The maximum is reached."
    planned = sum((item.amount_chf for item in payload.planned), Decimal(0))
    text += f". {_chf(amount=missing)} are missing to the maximum"
    if planned >= missing:
        return f"{text}; the planned transfers cover it."
    if planned > 0:
        return f"{text}; the planned transfers leave {_chf(amount=missing - planned)} open."
    return f"{text} by 31.12."


def _reminder(row: BillRow, today: date) -> str:
    return (
        f"The payment to {row.payee} ({_chf(amount=row.amount_chf)}) is a reminder, due "
        f"{_in_days(day=row.due, today=today)}: it cannot wait."
    )


def _row(row: BillRow) -> str:
    return f"{row.payee} with {_chf(amount=row.amount_chf)} on {_day(day=row.due)}"


def _in_days(day: date, today: date) -> str:
    days = (day - today).days
    if days <= 0:
        return "today"
    if days == 1:
        return "tomorrow"
    return f"in {days} days"


def _ordinal(day: int) -> str:
    suffix = "th" if 10 <= day % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def _chf(amount: Decimal) -> str:
    return f"CHF {amount:,.2f}".replace(",", "'")


def _day(day: date) -> str:
    return f"{day.day:02d}.{day.month:02d}."


def _date(day: date) -> str:
    return f"{day.day:02d}.{day.month:02d}.{day.year}"


def _month(month: str) -> str:
    return MONTH_NAMES[int(month[5:7]) - 1]


def _count(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"
