"""Expected answers to the reference questions per demo customer, computed from the seed CSVs."""

import csv
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[3] / "starter/resources/Demodaten/Daten_CSV"
CUSTOMERS = {
    "lukas": "P1_Lukas_Meier",
    "jana": "P2_Jana_Widmer",
    "daniela": "P3_Daniela_Ruegg",
    "marco": "P4_Marco_Baumann",
}
# The demo's today is 27.11.2026, the last booking day 26.11.2026.
LAST_MONTH = "2026-10"
RENT_MONTHS = ["2026-08", "2026-09", "2026-10", "2026-11"]
SPENDING_MONTHS = ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]
TODAY = "2026-11-27"
DUE_FROM, DUE_TO = TODAY, "2026-12-26"
SALARY_MONTH = "2026-11"
INTEREST_YEAR = "2025"
# Online shops and marketplaces; IKEA and Interdiscount count only for their online orders.
ONLINE_SHOPS = re.compile(
    r"galaxus|digitec|microspot|brack|zalando|amazon|aliexpress|etsy|blacksocks|ricardo|vinted"
    r"|ikea online|interdiscount\.ch",
    re.IGNORECASE,
)
OWN_TRANSFER_TYPES = {"account_transfer", "securities_buy"}
# A credit of these types is a merchant's refund, so it reduces spending.
REFUND_TYPES = {"debit_card", "twint_merchant"}


@dataclass(frozen=True)
class Movement:
    id: str
    date: str
    # Negative is money spent, positive a refund.
    amount: Decimal
    text: str


@dataclass(frozen=True)
class Answer:
    question: str
    figure: str
    ids: list[str]


def chf(amount: Decimal) -> str:
    sign = "-" if amount < 0 else ""
    whole, cents = f"{abs(amount):.2f}".split(".")
    return f"CHF {sign}{int(whole):,}.{cents}".replace(",", "'")


def read_rows(folder: Path, name: str) -> list[dict[str, str]]:
    with (folder / f"{name}.csv").open(encoding="utf-8") as file:
        return list(csv.DictReader(file))


def compact(iban: str) -> str:
    return iban.replace(" ", "").upper()


def read_movements(folder: Path) -> list[Movement]:
    own_ibans = {compact(iban=row["iban"]) for row in read_rows(folder=folder, name="accounts")}
    movements = []
    for row in read_rows(folder=folder, name="bookings"):
        amount = Decimal(row["amount"])
        kind = row["transaction_type"]
        is_own = kind in OWN_TRANSFER_TYPES or compact(iban=row["counterparty_iban"]) in own_ibans
        # The card bill is replaced by the card's purchases below.
        if is_own or kind == "card_settlement":
            continue
        if amount > 0 and kind not in REFUND_TYPES:
            continue
        text = f"{row['booking_text']} {row['counterparty_name']}"
        movements.append(
            Movement(id=row["booking_id"], date=row["booking_date"], amount=amount, text=text)
        )
    for row in read_rows(folder=folder, name="card_transactions"):
        # The card lists a purchase as positive and a refund as negative.
        movements.append(
            Movement(
                id=row["card_transaction_id"],
                date=row["transaction_date"],
                amount=-Decimal(row["amount_chf"]),
                text=f"{row['merchant_text']} {row['merchant_name']}",
            )
        )
    return movements


def online_shops(movements: list[Movement]) -> Answer:
    matches = [
        movement
        for movement in movements
        if movement.date.startswith(LAST_MONTH) and ONLINE_SHOPS.search(movement.text) is not None
    ]
    spent = -sum((movement.amount for movement in matches), Decimal(0))
    return Answer(
        question=f"Online shops in {LAST_MONTH}, refunds netted",
        figure=f"{chf(amount=spent)} in {len(matches)} movements",
        ids=[movement.id for movement in matches],
    )


def rent_label(row: dict[str, str]) -> str:
    purpose = re.search(r"miete \w+", row["booking_text"], re.IGNORECASE)
    label = row["booking_text"] if purpose is None else purpose.group(0)
    return f"{chf(amount=-Decimal(row['amount']))} ({label})"


def rent(folder: Path) -> Answer:
    paid: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_rows(folder=folder, name="bookings"):
        month = row["booking_date"][:7]
        is_rent = re.search(r"\bmiete\b", row["booking_text"], re.IGNORECASE) is not None
        if month in RENT_MONTHS and is_rent and Decimal(row["amount"]) < 0:
            paid[month].append(row)
    if not paid:
        return Answer(question="Rent paid per month", figure="no rent booked: pays no rent", ids=[])
    # Rent is booked at the end of the month before the one it pays for.
    months = [
        f"{month}: " + (", ".join(rent_label(row=row) for row in paid[month]) or "not booked")
        for month in RENT_MONTHS
    ]
    return Answer(
        question="Rent paid per booking month",
        figure="; ".join(months),
        ids=[row["booking_id"] for month in RENT_MONTHS for row in paid[month]],
    )


def monthly_spending(movements: list[Movement]) -> Answer:
    by_month = {month: Decimal(0) for month in SPENDING_MONTHS}
    ids = []
    for movement in movements:
        month = movement.date[:7]
        if month in by_month:
            by_month[month] -= movement.amount
            ids.append(movement.id)
    return Answer(
        question="Spending per month, card purchases instead of the bill",
        figure="; ".join(f"{month}: {chf(amount=amount)}" for month, amount in by_month.items()),
        ids=ids,
    )


def due_payments(folder: Path) -> Answer:
    due = [
        row
        for row in read_rows(folder=folder, name="upcoming_payments")
        if DUE_FROM <= row["due_date"] <= DUE_TO
    ]
    total = sum((Decimal(row["amount"]) for row in due), Decimal(0))
    return Answer(
        question=f"Payments due {DUE_FROM} to {DUE_TO}",
        figure=f"{chf(amount=total)} in {len(due)} payments",
        ids=[f"{row['due_date']} {row['source_id']}" for row in due],
    )


def salary(folder: Path) -> Answer:
    paid = [
        row
        for row in read_rows(folder=folder, name="bookings")
        if row["transaction_type"] == "salary" and row["booking_date"].startswith(SALARY_MONTH)
    ]
    return Answer(
        question=f"Salary booked in {SALARY_MONTH}, to compare with the payslip",
        figure=", ".join(
            f"{chf(amount=Decimal(row['amount']))} on {row['booking_date']}" for row in paid
        )
        or "none",
        ids=[row["booking_id"] for row in paid],
    )


def savings(folder: Path) -> Answer:
    accounts = [
        row for row in read_rows(folder=folder, name="accounts") if row["type"] == "savings"
    ]
    total = sum((Decimal(row["current_balance"]) for row in accounts), Decimal(0))
    balances = ", ".join(
        f"{row['name']} {chf(amount=Decimal(row['current_balance']))}" for row in accounts
    )
    return Answer(
        question="Savings accounts today",
        figure=f"{chf(amount=total)} in all: {balances}",
        ids=[row["account_id"] for row in accounts],
    )


def mortgage(folder: Path) -> Answer:
    interest = [
        row
        for row in read_rows(folder=folder, name="loan_transactions")
        if row["type"] == "interest" and row["value_date"].startswith(INTEREST_YEAR)
    ]
    if not interest:
        return Answer(question="Mortgage", figure="no loan interest booked", ids=[])
    paid = sum((Decimal(row["amount"]) for row in interest), Decimal(0))
    loans = read_rows(folder=folder, name="loans")
    running = [row for row in loans if row["maturity_date"] >= TODAY]
    next_loan = min(running, key=lambda row: row["maturity_date"], default=None)
    maturity = (
        "no tranche still running"
        if next_loan is None
        else f"next {next_loan['number']} on {next_loan['maturity_date']}"
    )
    return Answer(
        question=f"Mortgage interest paid in {INTEREST_YEAR}, next tranche to mature",
        figure=f"{chf(amount=paid)} in {len(interest)} bookings; {maturity}",
        ids=[row["booking_id"] for row in interest],
    )


def reference(folder: Path) -> list[Answer]:
    movements = read_movements(folder=folder)
    return [
        online_shops(movements=movements),
        rent(folder=folder),
        monthly_spending(movements=movements),
        due_payments(folder=folder),
        salary(folder=folder),
        savings(folder=folder),
        mortgage(folder=folder),
    ]


def main() -> int:
    for login, folder_name in CUSTOMERS.items():
        print(f"\n## {login}")  # noqa: T201
        for answer in reference(folder=DATA_PATH / folder_name):
            print(f"- {answer.question}: {answer.figure}")  # noqa: T201
            print(f"  ids: {', '.join(answer.ids[:12])}{' ...' if len(answer.ids) > 12 else ''}")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
