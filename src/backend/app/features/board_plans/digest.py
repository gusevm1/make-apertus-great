"""The customer read from the banking API, and the signals found in it, without any model.

Every rule here works on evidence and thresholds; no rule knows a customer by name.
"""

import re
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from app.features.board_plans.schemas import Signal
from app.features.ledger.schemas import LedgerRow
from app.features.recurring_payments.schemas import RecurringPayments
from app.features.tiles.schemas import (
    AnyPayload,
    BillsUntilPaydayPayload,
    CardBillPayload,
    DueSoonPayload,
    IncomeAndSpendingPayload,
    MortgagePayload,
    NetWorthPayload,
    PaydayBalancePayload,
    Pillar3aPayload,
    SavingsGoalPayload,
)

FULL_MONTHS = 6
# A first tile is drawn large; its figure has to be a headline worth that.
HERO_TEMPLATES = {
    "payday_balance",
    "net_worth",
    "mortgage",
    "savings_goal",
    "income_and_spending",
    "expected_income",
    "due_soon",
    "pillar_3a",
    "bills_until_payday",
}
HERO_TOP = 3
AVERAGE_MONTHS = 3
TOP_PAYEES = 25
TOP_PAYEES_THIS_MONTH = 12
UPCOMING_DAYS = 30
# A regular income comes in at least this many of the last full months, at a steady amount.
INCOME_MONTHS = 4
INCOME_MONTHS_MIN = 3
INCOME_MIN_CHF = Decimal(100)
INCOME_STEADY_SHARE = Decimal("0.1")
# Days after its usual day before a regular income counts as late.
LATE_AFTER_DAYS = 3
# The day before payday is tight below this share of a month's spending...
TIGHT_SHARE = Decimal("0.15")
# ...when the savings beside it would not carry this many months either.
BUFFER_MONTHS = Decimal("1.5")
GOAL_FAR_PERCENT = 25
REMINDER_WORDS = re.compile(r"mahnung|mahngeb|reminder|rappel|betreibung", re.IGNORECASE)
TAX_WORDS = re.compile(r"steuer|tax|impôt", re.IGNORECASE)
LOAN_WORDS = re.compile(r"darlehen|rückzahlung|loan|prêt", re.IGNORECASE)
REMINDER_DAYS = 14
# A one-off bill is large from this share of a month's income.
LARGE_BILL_SHARE = Decimal("0.15")
ONE_OFF_TYPES = {"qr_bill", "ebill", "domestic", "international"}
PRICE_RISE_SHARE = Decimal("0.05")
PRICE_RISE_DAYS = 365
FIXED_COST_SHARE = Decimal("0.5")
REGULAR_PAYEES_MAX = 6
NEGATIVE_MONTHS_MIN = 2
THIN_SAVINGS_MONTHS = 3
SAVINGS_TYPES = {"savings"}
PENSION_TYPES = {"pillar3a"}
CHF_AMOUNT = re.compile(r"CHF\s*([\d'’]+(?:\.\d+)?)")


@dataclass
class Raw:
    today: date
    customer: dict[str, Any]
    accounts: list[dict[str, Any]]
    upcoming: list[dict[str, Any]]
    loans: list[dict[str, Any]]
    portfolio: dict[str, Any]
    cards: list[dict[str, Any]]
    rows: list[LedgerRow]
    recurring: RecurringPayments


@dataclass
class Income:
    counterparty: str
    account_id: str
    usual_day: int
    amount: Decimal
    salary: bool
    arrived_this_month: bool
    late: bool
    # The booking text of its last payment, such as "Unterhalt Lina Dezember".
    text: str


@dataclass
class Month:
    month: str
    income: Decimal
    spending: Decimal


def chf(value: Decimal | float) -> str:
    """Swiss style, such as 1'050.00."""
    return f"{Decimal(str(value)):,.2f}".replace(",", "'")


def day(value: date) -> str:
    return value.strftime("%d.%m.%Y")


# Wording only; a tile with other words for the same figures is the same tile.
WORDING_ARGS = {"expected_label"}


def tile_key(template: str, args: dict[str, Any]) -> str:
    return f"{template}:{sorted((k, v) for k, v in args.items() if k not in WORDING_ARGS)}"


# --- facts -------------------------------------------------------------------------------------


def months(raw: Raw) -> list[Month]:
    """The last full months, oldest first, with what came in and what went out."""
    first_of_month = raw.today.replace(day=1)
    keys = []
    cursor = first_of_month
    for _ in range(FULL_MONTHS):
        cursor = (cursor - timedelta(days=1)).replace(day=1)
        keys.append(cursor.strftime("%Y-%m"))
    keys.reverse()
    income: dict[str, Decimal] = defaultdict(Decimal)
    spending: dict[str, Decimal] = defaultdict(Decimal)
    for row in raw.rows:
        key = row.date.strftime("%Y-%m")
        if row.kind == "credit":
            income[key] += row.amount_chf
        elif row.kind == "spending":
            spending[key] -= row.amount_chf
    return [Month(month=key, income=income[key], spending=spending[key]) for key in keys]


def average_spending(raw: Raw) -> Decimal:
    recent = months(raw=raw)[-AVERAGE_MONTHS:]
    return sum((month.spending for month in recent), Decimal(0)) / len(recent)


def incomes(raw: Raw) -> list[Income]:
    """Salaries and other incomes that come every month at a steady amount."""
    this_month = raw.today.strftime("%Y-%m")
    earlier = {m.month for m in months(raw=raw)[-INCOME_MONTHS:]}
    by_counterparty: dict[str, list[LedgerRow]] = defaultdict(list)
    for row in raw.rows:
        if row.kind == "credit" and row.source == "booking" and row.counterparty is not None:
            by_counterparty[row.counterparty].append(row)
    found: list[Income] = []
    for counterparty, rows in by_counterparty.items():
        salary = any(row.transaction_type == "salary" for row in rows)
        recent = [row for row in rows if row.date.strftime("%Y-%m") in earlier]
        if len({row.date.strftime("%Y-%m") for row in recent}) < INCOME_MONTHS_MIN:
            continue
        amount = Decimal(statistics.median(row.amount_chf for row in recent))
        if amount < INCOME_MIN_CHF:
            continue
        steady = [r for r in recent if abs(r.amount_chf - amount) <= amount * INCOME_STEADY_SHARE]
        if len(steady) < INCOME_MONTHS_MIN:
            continue
        usual_day = int(statistics.median(row.date.day for row in steady))
        arrived = any(
            row.date.strftime("%Y-%m") == this_month
            and abs(row.amount_chf - amount) <= amount * INCOME_STEADY_SHARE
            for row in rows
        )
        found.append(
            Income(
                counterparty=counterparty,
                account_id=steady[-1].account_id,
                usual_day=usual_day,
                amount=amount,
                salary=salary,
                arrived_this_month=arrived,
                late=not arrived and raw.today.day > usual_day + LATE_AFTER_DAYS,
                text=steady[-1].text,
            )
        )
    return sorted(found, key=lambda income: (not income.salary, -income.amount))


def top_payees(raw: Raw, since: date, until: date, limit: int) -> list[tuple[str, Decimal, int]]:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    counts: dict[str, int] = defaultdict(int)
    for row in raw.rows:
        if row.kind == "spending" and since <= row.date <= until:
            name = row.counterparty or row.text
            totals[name] -= row.amount_chf
            counts[name] += 1
    ranked = sorted(totals, key=lambda name: totals[name], reverse=True)[:limit]
    return [(name, totals[name], counts[name]) for name in ranked]


def upcoming_within(raw: Raw, days: int) -> list[dict[str, Any]]:
    until = raw.today + timedelta(days=days)
    return [p for p in raw.upcoming if date.fromisoformat(p["due_date"]) <= until]


def goal_amount(goal: str | None) -> Decimal | None:
    if goal is None:
        return None
    match = CHF_AMOUNT.search(goal)
    if match is None:
        return None
    return Decimal(match.group(1).replace("'", "").replace("’", ""))


def facts_text(raw: Raw) -> str:
    """What the model reads about the customer besides the signals."""
    customer = raw.customer
    lines = [f"Today: {day(raw.today)}", "Profile:"]
    for key in ("occupation", "civil_status", "children", "savings_goal", "property"):
        if customer.get(key) is not None:
            lines.append(f"- {key.replace('_', ' ')}: {customer[key]}")
    lines.append("Accounts (id, name, type, balance CHF, purpose, goal):")
    for account in raw.accounts:
        goal = f", goal: {account['savings_goal']}" if account.get("savings_goal") else ""
        lines.append(
            f"- {account['account_id']} {account['name']} ({account['type']}) "
            f"{chf(account['current_balance_chf'])}, purpose: {account.get('purpose')}{goal}"
        )
    if raw.portfolio.get("total_value_chf"):
        lines.append(
            f"Depot: worth {chf(raw.portfolio['total_value_chf'])}, "
            f"paid in {chf(raw.portfolio['invested_chf'])}"
        )
    for loan in raw.loans:
        lines.append(
            f"Loan {loan['loan_id']}: {loan['product']} {chf(loan['balance'])} at "
            f"{loan['interest_rate']} %, matures {loan['maturity_date']}"
        )
    for card in raw.cards:
        lines.append(f"Card {card['card_id']}: {card['product']} ({card['type']})")
    lines.append("Regular incomes (from, into account, usual day, amount, this month):")
    for income in incomes(raw=raw):
        state = "arrived" if income.arrived_this_month else "not arrived yet"
        label = "salary" if income.salary else "transfer"
        lines.append(
            f"- {income.counterparty} ({label}) into {income.account_id}, around day "
            f"{income.usual_day}, {chf(income.amount)}, {state}, booked as \"{income.text}\""
        )
    lines.append("Months (came in / went out, CHF):")
    for month in months(raw=raw):
        lines.append(f"- {month.month}: {chf(month.income)} / {chf(month.spending)}")
    windows = payee_windows(raw=raw)
    for period, since, until, limit in windows:
        lines.append(
            f"Largest payees, period {period} ({day(since)} to {day(until)}), as the bookings "
            "name them (total, count):"
        )
        for name, total, count in top_payees(raw=raw, since=since, until=until, limit=limit):
            lines.append(f"- {name}: {chf(total)} ({count}x)")
    lines.append("Recurring payments (payee, cadence, last amount):")
    for payment in raw.recurring.recurring:
        if payment.active:
            lines.append(f"- {payment.payee}, {payment.cadence}, {chf(payment.last_paid_chf)}")
    for plan in raw.recurring.instalment_plans:
        if plan.left > 0:
            lines.append(
                f"Instalment plan: {plan.payee}, {plan.paid} of {plan.total} paid, "
                f"{chf(plan.instalment_chf)} each"
            )
    lines.append(f"Upcoming payments of the next {UPCOMING_DAYS} days (due, payee, CHF, text, id):")
    for payment in upcoming_within(raw=raw, days=UPCOMING_DAYS):
        lines.append(
            f"- {payment['due_date']} {payment['payee_name']} {chf(payment['amount_chf'])} "
            f'"{payment["description"][:80]}" [{payment["source_id"]}]'
        )
    return "\n".join(lines)


def payee_windows(raw: Raw) -> list[tuple[str, date, date, int]]:
    """The periods of merchant_spending the facts list the largest payees for."""
    month_start = raw.today.replace(day=1)
    three_back = month_start
    for _ in range(AVERAGE_MONTHS):
        three_back = (three_back - timedelta(days=1)).replace(day=1)
    return [
        ("last_3_months", three_back, month_start - timedelta(days=1), TOP_PAYEES),
        ("this_month", month_start, raw.today, TOP_PAYEES_THIS_MONTH),
    ]


def names(raw: Raw) -> list[str]:
    """Every name an own tile may use: payees, account ids and upcoming payment ids."""
    found = [
        name
        for _, since, until, limit in payee_windows(raw=raw)
        for name, _, _ in top_payees(raw=raw, since=since, until=until, limit=limit)
    ]
    found += [payment["payee_name"] for payment in raw.upcoming]
    found += [account["account_id"] for account in raw.accounts]
    found += [p["source_id"] for p in upcoming_within(raw=raw, days=UPCOMING_DAYS)]
    return list(dict.fromkeys(found))


# --- the tiles worth resolving, then the signals in them -----------------------------------


def salary_account(raw: Raw) -> str | None:
    salaries = [income for income in incomes(raw=raw) if income.salary]
    return salaries[0].account_id if salaries else None


def late_income(raw: Raw) -> Income | None:
    late = [income for income in incomes(raw=raw) if income.late and not income.salary]
    return late[0] if late else None


def candidates(raw: Raw) -> list[tuple[str, dict[str, Any]]]:
    """Every tile a signal could need, to be resolved before the rules read them."""
    found: list[tuple[str, dict[str, Any]]] = []
    account = salary_account(raw=raw)
    if account is not None:
        late = late_income(raw=raw)
        payday_args: dict[str, Any] = {"account_id": account}
        if late is not None:
            payday_args["expected_from"] = late.counterparty
        found.append(("payday_balance", payday_args))
        found.append(("bills_until_payday", {"account_id": account}))
    for income in incomes(raw=raw):
        if not income.salary:
            found.append(("expected_income", {"counterparty": income.counterparty}))
    for acc in raw.accounts:
        if acc["type"] in SAVINGS_TYPES and goal_amount(goal=acc.get("savings_goal")) is not None:
            found.append(("savings_goal", {"account_id": acc["account_id"]}))
    for payment in _notable_bills(raw=raw):
        found.append(("bill", {"payment_id": payment["source_id"]}))
    found.append(("net_worth", {}))
    if raw.portfolio.get("total_value_chf"):
        found.append(("securities", {}))
    if any(acc["type"] in PENSION_TYPES for acc in raw.accounts):
        found.append(("pillar_3a", {}))
    for card in raw.cards:
        if card["type"] == "credit":
            found.append(("card_bill", {"card_id": card["card_id"]}))
    found.append(("due_soon", {"days": 30}))
    if raw.loans:
        found.append(("mortgage", {}))
    for payees in _payee_groups(raw=raw).values():
        found.append(("regular_payments", {"payees": payees}))
    found.append(("income_and_spending", {"months": 6}))
    found.append(("monthly_spending", {"months": 6}))
    savings = [acc["account_id"] for acc in raw.accounts if acc["type"] in SAVINGS_TYPES]
    if len(savings) >= 2:
        found.append(("account_balances", {"account_ids": savings}))
    return found


def _notable_bills(raw: Raw) -> list[dict[str, Any]]:
    monthly_payees = {p.payee for p in raw.recurring.recurring if p.cadence == "monthly"}
    salaries = [income.amount for income in incomes(raw=raw) if income.salary]
    income = salaries[0] if salaries else Decimal(0)
    notable = []
    for payment in upcoming_within(raw=raw, days=UPCOMING_DAYS):
        due = date.fromisoformat(payment["due_date"])
        text = f"{payment['description']} {payment['payee_name']}"
        reminder = REMINDER_WORDS.search(text) and due <= raw.today + timedelta(days=REMINDER_DAYS)
        large = (
            payment["type"] in ONE_OFF_TYPES
            and payment["payee_name"] not in monthly_payees
            and Decimal(str(payment["amount_chf"])) >= income * LARGE_BILL_SHARE
        )
        if reminder or large:
            notable.append(payment)
    return notable


def _upcoming_payees(raw: Raw) -> list[str]:
    return list(dict.fromkeys(payment["payee_name"] for payment in raw.upcoming))


def _payee_groups(raw: Raw) -> dict[str, list[str]]:
    """Named groups of payees worth a regular_payments tile, each from the upcoming payments."""
    upcoming = _upcoming_payees(raw=raw)
    groups: dict[str, list[str]] = {}
    risen = [
        payment.payee
        for payment in raw.recurring.recurring
        if payment.active
        and payment.cadence != "yearly"
        and payment.payee in upcoming
        and _recent_rise(raw=raw, payee=payment.payee)
    ]
    if risen:
        groups["price_rise"] = risen[:REGULAR_PAYEES_MAX]
    lenders = [
        payment["payee_name"]
        for payment in raw.upcoming
        if payment["type"] == "standing_order" and LOAN_WORDS.search(payment["description"])
    ]
    if lenders:
        groups["private_loan"] = list(dict.fromkeys(lenders))[:REGULAR_PAYEES_MAX]
    plans = [
        plan.payee
        for plan in raw.recurring.instalment_plans
        if plan.left > 0 and plan.payee in upcoming
    ]
    if plans:
        groups["instalments"] = list(dict.fromkeys(plans))[:REGULAR_PAYEES_MAX]
    fixed = [
        payment.payee
        for payment in raw.recurring.recurring
        if payment.active and payment.cadence == "monthly" and payment.payee in upcoming
    ]
    if fixed:
        groups["fixed_costs"] = fixed[:REGULAR_PAYEES_MAX]
    return groups


def _recent_rise(raw: Raw, payee: str) -> bool:
    payment = next(p for p in raw.recurring.recurring if p.payee == payee)
    since = raw.today - timedelta(days=PRICE_RISE_DAYS)
    return any(
        change.date >= since and change.new_price >= change.old_price * (1 + PRICE_RISE_SHARE)
        for change in payment.price_changes
    )


def signals(raw: Raw, resolved: dict[str, AnyPayload]) -> list[Signal]:
    """The findings, strongest first, each with its tile when that tile resolved."""
    found: list[Signal] = []

    def add(kind: str, text: str, strength: int, template: str | None, args: dict[str, Any]):
        payload_ok = template is None or tile_key(template, args) in resolved
        found.append(
            Signal(
                id="",
                kind=kind,
                text=text,
                strength=strength,
                template=template if payload_ok else None,  # type: ignore[arg-type]
                args=args if payload_ok and template is not None else None,
            )
        )

    def get(template: str, args: dict[str, Any]) -> Any:
        return resolved.get(tile_key(template, args))

    spending = average_spending(raw=raw)
    savings_total = sum(
        (
            Decimal(str(a["current_balance_chf"]))
            for a in raw.accounts
            if a["type"] in SAVINGS_TYPES
        ),
        Decimal(0),
    )
    account = salary_account(raw=raw)
    tight = False
    if account is not None:
        late = late_income(raw=raw)
        payday_args: dict[str, Any] = {"account_id": account}
        if late is not None:
            payday_args["expected_from"] = late.counterparty
        payday: PaydayBalancePayload | None = get("payday_balance", payday_args)
        if payday is not None:
            left = payday.figure_chf
            tight = (
                left < spending * TIGHT_SHARE and left + savings_total < spending * BUFFER_MONTHS
            )
            text = (
                f"On {day(payday.day_before)}, the day before the next salary, "
                f"{chf(left)} is left on {payday.account_name} after "
                f"{payday.upcoming_count} payments, {chf(payday.per_day_chf)} a day"
            )
            if payday.alternative is not None:
                text += (
                    f"; if the money from {payday.alternative.counterparty} arrives, "
                    f"{chf(payday.alternative.left_chf)}"
                )
            text += f". A month's spending is about {chf(spending)}."
            add(
                "payday_tight" if tight else "payday",
                text,
                100 if tight else 20,
                # Only a tight payday is worth a tile; for others it is a fact.
                "payday_balance" if tight else None,
                payday_args,
            )
        bills: BillsUntilPaydayPayload | None = get("bills_until_payday", {"account_id": account})
        if bills is not None and len(bills.rows) >= 3:
            add(
                "bills_before_payday",
                f"{len(bills.rows)} payments of together {chf(bills.figure_chf)} leave before "
                f"the salary on {day(bills.payday)}.",
                60 if tight else 15,
                "bills_until_payday",
                {"account_id": account},
            )
    for income in incomes(raw=raw):
        if income.salary:
            continue
        if income.late:
            text = (
                f"The {chf(income.amount)} from {income.counterparty} usually arrive around "
                f"day {income.usual_day} and have not arrived this month."
            )
        else:
            text = (
                f"{income.counterparty} sends about {chf(income.amount)} every month, "
                f"around day {income.usual_day}."
            )
        add(
            "income_late" if income.late else "income_regular",
            text,
            90 if income.late else 10,
            "expected_income",
            {"counterparty": income.counterparty},
        )
    for acc in raw.accounts:
        args = {"account_id": acc["account_id"]}
        goal: SavingsGoalPayload | None = get("savings_goal", args)
        if goal is None:
            continue
        text = (
            f"{goal.account_name} holds {chf(acc['current_balance_chf'])}, "
            f'{goal.percent:.0f} % of its goal "{goal.goal_text}"'
        )
        if goal.month_change_chf < 0:
            text += f"; {chf(-goal.month_change_chf)} went out of it this month"
        text += "."
        if goal.percent < GOAL_FAR_PERCENT:
            strength, kind = 70, "goal_far"
        elif goal.percent < 100:
            strength, kind = 40, "goal_progress"
        else:
            strength, kind = 25, "goal_reached"
        add(kind, text, strength, "savings_goal", args)
    for payment in _notable_bills(raw=raw):
        args = {"payment_id": payment["source_id"]}
        text = (
            f"{payment['payee_name']} is due on {day(date.fromisoformat(payment['due_date']))}: "
            f'{chf(payment["amount_chf"])}, "{payment["description"][:90]}".'
        )
        reminder = REMINDER_WORDS.search(payment["description"]) is not None
        kind = (
            "reminder"
            if reminder
            else "tax_bill"
            if TAX_WORDS.search(f"{payment['description']} {payment['payee_name']}")
            else "large_bill"
        )
        add(kind, text, 85 if reminder else 35, "bill", args)
    worth: NetWorthPayload | None = get("net_worth", {})
    if worth is not None:
        parts = {part.group: part.value_chf for part in worth.parts}
        accounts_value = parts.get("accounts", Decimal(0))
        securities_value = parts.get("securities", Decimal(0))
        text = (
            f"Without pillar 3a the customer owns {chf(worth.figure_chf)}: "
            + ", ".join(f"{group} {chf(value)}" for group, value in parts.items())
            + "."
        )
        if securities_value > accounts_value:
            add(
                "depot_large",
                text + " The depot is worth more than all accounts.",
                80,
                "net_worth",
                {},
            )
        elif securities_value > 0:
            add("net_worth", text, 15, "net_worth", {})
    if raw.portfolio.get("total_value_chf"):
        add(
            "securities",
            f"The depot is worth {chf(raw.portfolio['total_value_chf'])}, "
            f"{chf(raw.portfolio['invested_chf'])} were paid in.",
            40,
            "securities",
            {},
        )
    pillar: Pillar3aPayload | None = get("pillar_3a", {})
    if pillar is not None:
        missing = pillar.figure_chf
        text = (
            f"Paid into pillar 3a in {pillar.year}: {chf(pillar.paid_chf)} of the maximum "
            f"{chf(pillar.maximum_chf)}; after the standing orders {chf(missing)} is missing"
        )
        if pillar.planned:
            text += f", covered by {len(pillar.planned)} planned transfer(s)"
        text += "."
        strength = 45 if 0 < missing <= pillar.maximum_chf / 2 else 35 if missing > 0 else 20
        add("pillar_3a", text, strength, "pillar_3a", {})
    for card in raw.cards:
        args = {"card_id": card["card_id"]}
        statement: CardBillPayload | None = get("card_bill", args)
        if statement is None:
            continue
        flag = " (provisional)" if statement.flag == "provisional" else ""
        due = f", collected on {day(statement.due)}" if statement.due is not None else ""
        add(
            "card_bill",
            f"The {statement.card_name} bill for {statement.period} is "
            f"{chf(statement.figure_chf)}{flag}{due}, {statement.purchases} purchases.",
            50,
            "card_bill",
            args,
        )
    soon: DueSoonPayload | None = get("due_soon", {"days": 30})
    if soon is not None:
        balance = next(
            (
                Decimal(str(a["current_balance_chf"]))
                for a in raw.accounts
                if a["account_id"] == account
            ),
            Decimal(0),
        )
        pressing = soon.figure_chf > balance
        add(
            "due_soon",
            f"{soon.count} payments of together {chf(soon.figure_chf)} are due in the next "
            "30 days" + (", more than the salary account holds today." if pressing else "."),
            75 if pressing else 35,
            "due_soon",
            {"days": 30},
        )
    mortgage: MortgagePayload | None = get("mortgage", {})
    if mortgage is not None:
        text = (
            f"The mortgage is {chf(mortgage.figure_chf)} in {len(mortgage.tranches)} tranches, "
            f"{chf(mortgage.annual_interest_chf)} interest a year"
        )
        if mortgage.next_maturity is not None and mortgage.next_maturity.maturity_date:
            text += (
                f"; the tranche {mortgage.next_maturity.product} of "
                f"{chf(mortgage.next_maturity.balance_chf)} runs out on "
                f"{day(mortgage.next_maturity.maturity_date)} and needs a decision"
            )
        add(
            "mortgage_maturity" if mortgage.next_maturity else "mortgage",
            text + ".",
            95 if mortgage.next_maturity else 50,
            "mortgage",
            {},
        )
    groups = _payee_groups(raw=raw)
    for group, payees in groups.items():
        args = {"payees": payees}
        if group == "price_rise":
            rises = []
            for payee in payees:
                payment = next(p for p in raw.recurring.recurring if p.payee == payee)
                change = payment.price_changes[-1]
                rises.append(
                    f"{payee} from {chf(change.old_price)} to {chf(change.new_price)} "
                    f"on {day(change.date)}"
                )
            add(
                "price_rise",
                "Regular payments that cost more within a year: " + "; ".join(rises) + ".",
                30,
                "regular_payments",
                args,
            )
        elif group == "private_loan":
            add(
                "private_loan",
                "A standing order repays a private loan to " + ", ".join(payees) + ".",
                45,
                "regular_payments",
                args,
            )
        elif group == "instalments":
            plans = [
                f"{plan.payee} ({plan.paid} of {plan.total} paid, {chf(plan.left_chf)} left)"
                for plan in raw.recurring.instalment_plans
                if plan.left > 0 and plan.payee in payees
            ]
            add(
                "instalments",
                "Instalment plans running: " + "; ".join(plans) + ".",
                40,
                "regular_payments",
                args,
            )
        else:
            fixed = sum(
                (p.last_paid_chf for p in raw.recurring.recurring if p.payee in payees),
                Decimal(0),
            )
            income = sum((i.amount for i in incomes(raw=raw)), Decimal(0))
            large = income > 0 and fixed >= income * FIXED_COST_SHARE
            add(
                "fixed_costs",
                f"The {len(payees)} largest monthly payments add up to {chf(fixed)} a month"
                + (", half of the income or more." if large else "."),
                45 if large else 15,
                "regular_payments",
                args,
            )
    cashflow: IncomeAndSpendingPayload | None = get("income_and_spending", {"months": 6})
    if cashflow is not None:
        negative = [m.month for m in cashflow.months if m.left_chf < 0]
        # Months in the red weigh only when the savings beside them are thin.
        thin = savings_total < spending * THIN_SAVINGS_MONTHS
        pressing = len(negative) >= NEGATIVE_MONTHS_MIN and thin
        text = f"On average {chf(cashflow.figure_chf)} was left per month over the last 6 months"
        if len(negative) >= NEGATIVE_MONTHS_MIN:
            text += (
                f"; in {len(negative)} months more went out than came in ({', '.join(negative)})"
            )
        add(
            "cashflow_negative" if pressing else "cashflow",
            text + ".",
            45 if pressing else 25,
            "income_and_spending",
            {"months": 6},
        )
    spent = get("monthly_spending", {"months": 6})
    if spent is not None:
        add(
            "spending",
            f"Spending averaged {chf(spent.figure_chf)} a month over the last 6 "
            f"months, highest in {spent.highest}.",
            20,
            "monthly_spending",
            {"months": 6},
        )
    savings = [acc["account_id"] for acc in raw.accounts if acc["type"] in SAVINGS_TYPES]
    if len(savings) >= 2:
        names = [
            f"{a['name']} ({a.get('purpose')})" for a in raw.accounts if a["account_id"] in savings
        ]
        add(
            "savings_pots",
            f"{len(savings)} savings accounts with their own purpose: " + "; ".join(names) + ".",
            30 if len(savings) >= 3 else 15,
            "account_balances",
            {"account_ids": savings},
        )

    found.sort(key=lambda signal: -signal.strength)
    for index, signal in enumerate(found, start=1):
        signal.id = f"S{index}"
    return found


def label(signal: Signal) -> str:
    """The signal as the model names it: id, kind and template, so a title cannot drift."""
    return f"{signal.id} {signal.kind} {signal.template}"


def signals_text(signals: list[Signal]) -> str:
    lines = []
    for signal in signals:
        if signal.template is None:
            lines.append(f"(fact, no tile) {signal.text}")
            continue
        headline = " (can be the hero)" if signal.template in HERO_TEMPLATES else ""
        lines.append(f"{label(signal=signal)}{headline}: {signal.text}")
    return "\n".join(lines)


# The kinds that decide the question, in the order the server proposes them as the hero.
HERO_KINDS = ["payday_tight", "mortgage_maturity", "depot_large", "cashflow_negative"]


def hero_candidates(signals: list[Signal]) -> list[Signal]:
    """The signals the hero may be: the one a deciding kind names, else the strongest headlines."""
    top = [s for s in signals if s.template in HERO_TEMPLATES][:HERO_TOP]
    rank = {kind: index for index, kind in enumerate(HERO_KINDS)}
    ranked = sorted(top, key=lambda s: rank.get(s.kind, len(HERO_KINDS)))
    # A deciding kind fixes the hero; the model still writes the kind, question and title.
    return ranked[:1] if ranked and ranked[0].kind in rank else ranked


# --- what a requested board may be built from -------------------------------------------------

REQUEST_MONTHS = 12
REQUEST_SHOPS = 25
REQUEST_PAYMENT_DAYS = 60
# What an income is, from its booking text, in the customer's English words.
INCOME_WORDS = [
    (re.compile(r"unterhalt|alimente", re.IGNORECASE), "the child support"),
    (re.compile(r"kinderzulage|familienzulage", re.IGNORECASE), "the child allowance"),
    (re.compile(r"stipendium", re.IGNORECASE), "the grant"),
    (re.compile(r"\brente\b|pension", re.IGNORECASE), "the pension"),
    (re.compile(r"miete|mietzins", re.IGNORECASE), "the rent"),
]


@dataclass
class RequestLists:
    """The customer's things a requested board can show, each list keyed by what the model picks."""

    accounts: dict[str, dict[str, Any]]
    # Upcoming payee: the texts of its payments.
    payees: dict[str, str]
    # Payee of the bookings of the last year: a booking text and the total.
    shops: dict[str, str]
    # Open single payment id: its line.
    payments: dict[str, str]
    # Payees that a standing order repays a private loan to.
    lenders: list[str]


def income_label(text: str) -> str | None:
    """The customer's words for an income from its booking text, such as "the child support"."""
    for pattern, label in INCOME_WORDS:
        if pattern.search(text):
            return label
    return None


def income_texts(raw: Raw) -> dict[str, str]:
    """The booking text of every regular income, by counterparty."""
    return {income.counterparty: income.text for income in incomes(raw=raw)}


def request_lists(raw: Raw) -> RequestLists:
    since = raw.today - timedelta(days=365)
    texts: dict[str, list[str]] = defaultdict(list)
    for payment in raw.upcoming:
        texts[payment["payee_name"]].append(payment["description"][:60])
    payees = {name: "; ".join(dict.fromkeys(found))[:120] for name, found in texts.items()}
    shops: dict[str, str] = {}
    booked: dict[str, str] = {}
    for row in raw.rows:
        if row.kind == "spending" and row.counterparty is not None:
            booked[row.counterparty] = row.text[:70]
    for name, total, count in top_payees(
        raw=raw, since=since, until=raw.today, limit=REQUEST_SHOPS
    ):
        if name in booked:
            shops[name] = f'{chf(total)} in {count} bookings, booked as "{booked[name]}"'
    payments = {
        payment["source_id"]: (
            f"{payment['due_date']} {payment['payee_name']} {chf(payment['amount_chf'])} "
            f'"{payment["description"][:80]}"'
        )
        for payment in upcoming_within(raw=raw, days=REQUEST_PAYMENT_DAYS)
        if payment["type"] in ONE_OFF_TYPES
    }
    accounts = {account["account_id"]: account for account in raw.accounts}
    return RequestLists(
        accounts=accounts,
        payees=payees,
        shops=shops,
        payments=payments,
        lenders=_payee_groups(raw=raw).get("private_loan", []),
    )


def request_text(lists: RequestLists) -> str:
    lines = ["Accounts (id: name, purpose, goal):"]
    for account_id, account in lists.accounts.items():
        goal = account.get("savings_goal") or "none"
        lines.append(f"- {account_id}: {account['name']}, {account.get('purpose')}, goal: {goal}")
    lines.append("Upcoming payees (name: what their payments say):")
    lines += [f"- {name}: {text}" for name, text in lists.payees.items()]
    lines.append("Payees of the last 12 months (name: what was paid, a booking text):")
    lines += [f"- {name}: {text}" for name, text in lists.shops.items()]
    lines.append("Open single payments (id: due, payee, amount, text):")
    lines += [f"- {payment_id}: {text}" for payment_id, text in lists.payments.items()]
    return "\n".join(lines)
