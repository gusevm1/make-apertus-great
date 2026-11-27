import csv
from decimal import Decimal
from pathlib import Path

from evals.reference import (
    CUSTOMERS,
    DATA_PATH,
    monthly_spending,
    online_shops,
    read_movements,
    reference,
    rent,
)

BOOKING_COLUMNS = [
    "booking_id",
    "booking_date",
    "amount",
    "booking_text",
    "counterparty_name",
    "counterparty_iban",
    "transaction_type",
]
CARD_COLUMNS = [
    "card_transaction_id",
    "transaction_date",
    "merchant_text",
    "merchant_name",
    "amount_chf",
]
OWN_IBAN = "CH00 0888 8000 0000 0000 1"


def write(folder: Path, name: str, columns: list[str], rows: list[list[str]]) -> None:
    with (folder / f"{name}.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        writer.writerows(rows)


def customer(tmp_path: Path, bookings: list[list[str]], card: list[list[str]]) -> Path:
    write(folder=tmp_path, name="accounts", columns=["iban"], rows=[[OWN_IBAN]])
    write(folder=tmp_path, name="bookings", columns=BOOKING_COLUMNS, rows=bookings)
    write(folder=tmp_path, name="card_transactions", columns=CARD_COLUMNS, rows=card)
    return tmp_path


def test_card_purchases_replace_the_card_bill(tmp_path: Path) -> None:
    folder = customer(
        tmp_path=tmp_path,
        bookings=[["BK-1", "2026-10-20", "-75.00", "Kreditkarte", "Visa", "", "card_settlement"]],
        card=[["CTX-1", "2026-10-03", "ZALANDO.CH", "Zalando", "75.00"]],
    )

    spending = monthly_spending(movements=read_movements(folder=folder))

    assert "2026-10: CHF 75.00" in spending.figure
    assert spending.ids == ["CTX-1"]


def test_own_transfers_are_not_spending(tmp_path: Path) -> None:
    folder = customer(
        tmp_path=tmp_path,
        bookings=[
            [
                "BK-1",
                "2026-10-01",
                "-500.00",
                "Dauerauftrag Sparen",
                "Ich",
                OWN_IBAN,
                "standing_order",
            ],
            ["BK-2", "2026-10-02", "-300.00", "ETF Kauf", "Depot", "", "securities_buy"],
            ["BK-3", "2026-10-03", "-20.00", "Kartenzahlung MIGROS", "Migros", "", "debit_card"],
        ],
        card=[],
    )

    spending = monthly_spending(movements=read_movements(folder=folder))

    assert "2026-10: CHF 20.00" in spending.figure
    assert spending.ids == ["BK-3"]


def test_refunds_are_netted_and_salary_is_not(tmp_path: Path) -> None:
    folder = customer(
        tmp_path=tmp_path,
        bookings=[
            ["BK-1", "2026-10-05", "-100.00", "GALAXUS.CH", "Galaxus", "", "debit_card"],
            ["BK-2", "2026-10-09", "40.00", "GALAXUS.CH Gutschrift", "Galaxus", "", "debit_card"],
            ["BK-3", "2026-10-25", "6000.00", "Lohn", "Arbeitgeber", "", "salary"],
        ],
        card=[["CTX-1", "2026-10-14", "DIGITEC.CH GUTSCHRIFT", "Digitec", "-10.00"]],
    )

    answer = online_shops(movements=read_movements(folder=folder))

    assert answer.figure == "CHF 50.00 in 3 movements"


def test_a_customer_without_rent_bookings_pays_no_rent(tmp_path: Path) -> None:
    folder = customer(
        tmp_path=tmp_path,
        bookings=[
            [
                "BK-1",
                "2026-10-28",
                "2200.00",
                "Gutschrift Anteil Miete",
                "Sara",
                "",
                "incoming_transfer",
            ]
        ],
        card=[],
    )

    assert rent(folder=folder).figure == "no rent booked: pays no rent"


def test_lukas_october_migros_bookings_match_the_banks_sum_and_the_card_adds_to_it() -> None:
    movements = read_movements(folder=DATA_PATH / CUSTOMERS["lukas"])

    migros = [m for m in movements if m.date.startswith("2026-10") and "migros" in m.text.lower()]
    bookings = [m for m in migros if m.id.startswith("BK-")]

    assert -sum(m.amount for m in bookings) == Decimal("413.77")
    assert -sum(m.amount for m in migros) == Decimal("430.05")


def test_every_customer_gets_four_answers() -> None:
    for folder_name in CUSTOMERS.values():
        assert len(reference(folder=DATA_PATH / folder_name)) == 4
