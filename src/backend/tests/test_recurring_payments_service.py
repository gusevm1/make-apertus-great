from datetime import date
from decimal import Decimal
from typing import Any

import httpx2
import pytest

from app.clients.banking import BankingClient
from app.core.config import get_settings
from app.features.ledger.service import LedgerService
from app.features.recurring_payments.schemas import RecurringPayments
from app.features.recurring_payments.service import RecurringPaymentService

TOKEN = "customer-token"
TODAY = date(2026, 11, 27)


def _months(first: date, count: int) -> list[date]:
    return [
        date(first.year + (first.month - 1 + step) // 12, (first.month - 1 + step) % 12 + 1, 5)
        for step in range(count)
    ]


class Bank:
    """Bookings and card purchases for the faked bank, numbered in the order they are added."""

    def __init__(self) -> None:
        self.bookings: list[dict[str, Any]] = []
        self.purchases: list[dict[str, Any]] = []

    def booking(self, day: date, amount: float, payee: str | None, text: str) -> None:
        self.bookings.append(
            {
                "booking_id": f"BK-{len(self.bookings) + 1:05d}",
                "account_id": "ACC-PRIV",
                "booking_date": day.isoformat(),
                "amount": amount,
                "booking_text": text,
                "counterparty_name": payee,
                "transaction_type": "direct_debit",
            }
        )

    def purchase(
        self, day: date, chf: float, original: float, currency: str, merchant: str = "Dropbox"
    ) -> None:
        self.purchases.append(
            {
                "card_transaction_id": f"CTX-{len(self.purchases) + 1:05d}",
                "card_id": "CARD-VISA",
                "transaction_date": day.isoformat(),
                "merchant_text": merchant.upper(),
                "merchant_name": merchant,
                "original_amount": original,
                "original_currency": currency,
                "amount_chf": chf,
                "statement_id": f"STMT-{day:%Y-%m}",
            }
        )


@pytest.fixture
def bank() -> Bank:
    bank = Bank()
    for number, day in enumerate(_months(first=date(2024, 1, 5), count=35)):
        bank.booking(day=day, amount=-17.9 if number < 24 else -20.9, payee="Netflix", text="Abo")
        bank.booking(day=day, amount=-80.0 - number * 3.1, payee="EKZ", text="Strom")
        bank.purchase(day=day, chf=round(10.5 + number * 0.03, 2), original=11.99, currency="USD")
    for day in (date(2024, 3, 1), date(2024, 6, 1), date(2024, 9, 2), date(2024, 12, 2)):
        bank.booking(day=day, amount=-84.0, payee="Serafe AG", text="Haushaltabgabe")
    for day, amount in ((date(2024, 7, 3), -1312.8), (date(2025, 7, 3), -1338.6)):
        bank.booking(day=day, amount=amount, payee="AXA", text="Motorfahrzeugversicherung")
    bank.booking(
        day=date(2026, 7, 3), amount=-1361.2, payee="AXA", text="Motorfahrzeugversicherung"
    )
    for day in _months(first=date(2024, 1, 5), count=6):
        bank.booking(day=day, amount=-12.0, payee="Old Gym", text="Abo")
    for number, day in enumerate(_months(first=date(2024, 1, 5), count=24)):
        prepayment = 1550.0 if number < 18 else 1450.0
        bank.booking(day=day, amount=-prepayment, payee="Steueramt", text="Vorauszahlung")
        if number in (4, 18):
            bank.booking(day=day, amount=-2140.0, payee="Steueramt", text="Schlussrechnung")
    for day, chf in ((date(2023, 12, 20), 276.4), (date(2024, 12, 20), 252.95)):
        bank.purchase(day=day, chf=chf, original=chf, currency="CHF", merchant="Jelmoli")
    bank.purchase(
        day=date(2025, 12, 20), chf=328.24, original=328.24, currency="CHF", merchant="Jelmoli"
    )
    for day in (date(2025, 2, 1), date(2025, 2, 9), date(2025, 8, 30)):
        bank.booking(day=day, amount=-40.0, payee="Reto Hauser", text="TWINT")
    for paid, day in enumerate(_months(first=date(2025, 11, 5), count=3), start=1):
        text = f"Lastschrift (LSV) Klarna Bank AB, IKEA Ratenkauf, Rate {paid}/3"
        bank.booking(day=day, amount=-620.0, payee="Klarna Bank AB", text=text)
    for paid, day in enumerate(_months(first=date(2025, 12, 5), count=6), start=1):
        text = f"Lastschrift (LSV) Klarna Bank AB, Interdiscount Finanzierung, Rate {paid}/6"
        bank.booking(day=day, amount=-89.0, payee="Klarna Bank AB", text=text)
    for paid, day in enumerate(_months(first=date(2025, 4, 5), count=20), start=1):
        text = f"Lastschrift (LSV) Ratenwerk Finanz AG, Ratenvertrag RW-2025-48817, Rate {paid}/24"
        bank.booking(day=day, amount=-77.8, payee="Ratenwerk Finanz AG", text=text)
    return bank


def _page(items: list[dict[str, Any]], request: httpx2.Request) -> httpx2.Response:
    offset, limit = int(request.url.params["offset"]), int(request.url.params["limit"])
    return httpx2.Response(200, json={"items": items[offset : offset + limit], "total": len(items)})


@pytest.fixture
async def found(bank: Bank) -> RecurringPayments:
    def handle(request: httpx2.Request) -> httpx2.Response:
        path = request.url.path.removeprefix("/api")
        if request.headers.get("authorization") != f"Bearer {TOKEN}":
            return httpx2.Response(401, json={"detail": "Not authenticated"})
        if path == "/accounts":
            return httpx2.Response(200, json={"items": []})
        if path == "/loan-transactions":
            return httpx2.Response(200, json={"items": []})
        if path == "/cards":
            card = {"card_id": "CARD-VISA", "type": "credit", "linked_account": "ACC-PRIV"}
            return httpx2.Response(200, json={"items": [card]})
        if path == "/bookings":
            return _page(items=bank.bookings, request=request)
        if path == "/cards/CARD-VISA/statements":
            return httpx2.Response(200, json={"items": []})
        if path == "/cards/CARD-VISA/transactions":
            return _page(items=bank.purchases, request=request)
        return httpx2.Response(404, json={"detail": "Not found"})

    http = httpx2.AsyncClient(
        transport=httpx2.MockTransport(handle), base_url=get_settings().banking_api_url
    )
    banking = BankingClient(settings=get_settings(), http_client=http)
    service = RecurringPaymentService(ledger=LedgerService(banking=banking))
    return await service.list_recurring(token=TOKEN, today=TODAY)


def _by_payee(found: RecurringPayments) -> dict[str, Any]:
    return {payment.payee: payment for payment in found.recurring}


async def test_payees_get_their_cadence_and_irregular_ones_none(found: RecurringPayments) -> None:
    cadences = {payee: payment.cadence for payee, payment in _by_payee(found=found).items()}

    assert cadences == {
        "Netflix": "monthly",
        "EKZ": "monthly",
        "Dropbox": "monthly",
        "Serafe AG": "quarterly",
        "AXA": "yearly",
        "Old Gym": "monthly",
        "Steueramt": "monthly",
        "Jelmoli": "yearly",
    }


async def test_a_price_rise_names_the_bookings_before_and_after(
    found: RecurringPayments, bank: Bank
) -> None:
    netflix = _by_payee(found=found)["Netflix"]

    (rise,) = netflix.price_changes
    assert (rise.old_price, rise.new_price, rise.currency) == (
        Decimal("17.9"),
        Decimal("20.9"),
        "CHF",
    )
    before = next(b for b in bank.bookings if b["booking_id"] == rise.id_before)
    after = next(b for b in bank.bookings if b["booking_id"] == rise.id_after)
    assert (before["amount"], after["amount"], after["booking_date"]) == (
        -17.9,
        -20.9,
        "2026-01-05",
    )
    # December 2025 at 17.90, then eleven months at 20.90.
    assert (netflix.last_paid_chf, netflix.paid_last_12_months_chf) == (
        Decimal("20.9"),
        Decimal("247.8"),
    )
    assert netflix.active
    assert netflix.next_expected == date(2026, 12, 5)


async def test_only_real_price_changes_are_listed(found: RecurringPayments) -> None:
    payments = _by_payee(found=found)

    assert payments["Dropbox"].price_changes == []
    assert payments["EKZ"].price_changes == []
    assert payments["Jelmoli"].price_changes == []
    (prepayment,) = payments["Steueramt"].price_changes
    assert (prepayment.old_price, prepayment.new_price) == (Decimal("1550.0"), Decimal("1450.0"))
    assert [change.new_price for change in payments["AXA"].price_changes] == [
        Decimal("1338.6"),
        Decimal("1361.2"),
    ]


async def test_a_payment_that_stopped_is_not_active(found: RecurringPayments) -> None:
    # Old Gym stopped in June 2024, long before today.
    assert not _by_payee(found=found)["Old Gym"].active


async def test_instalment_plans_count_what_is_left_and_stay_apart(
    found: RecurringPayments,
) -> None:
    plans = {plan.plan: plan for plan in found.instalment_plans}

    washing_machine = plans["Lastschrift (LSV) Ratenwerk Finanz AG, Ratenvertrag RW-2025-48817"]
    assert (washing_machine.paid, washing_machine.total, washing_machine.left) == (20, 24, 4)
    assert washing_machine.left_chf == Decimal("311.2")
    assert len(washing_machine.ids) == 20
    ikea = plans["Lastschrift (LSV) Klarna Bank AB, IKEA Ratenkauf"]
    interdiscount = plans["Lastschrift (LSV) Klarna Bank AB, Interdiscount Finanzierung"]
    assert (ikea.paid, ikea.left, interdiscount.paid, interdiscount.left) == (3, 0, 6, 0)
    assert "Klarna Bank AB" not in _by_payee(found=found)
