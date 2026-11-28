import json
from typing import Any

import httpx2
import pytest

from app.main import app
from tests.conftest import FakeApertus
from tests.test_transaction_tags import _bank_client, _booking, _categorise_only, _rows_of, _tags

BOOKINGS = [
    _booking(
        "BK-1",
        -640.2,
        "Zahlung QR-Rechnung Garage Sihltal AG, Jahresservice VW Golf 2024",
        counterparty_name="Garage Sihltal AG",
    ),
    _booking(
        "BK-2",
        -1120.8,
        "Zahlung QR-Rechnung Garage Sihltal AG, Jahresservice VW Golf 2025",
        counterparty_name="Garage Sihltal AG",
    ),
    _booking(
        "BK-3",
        -124.0,
        "Zahlung QR-Rechnung Garage Sihltal AG, Radwechsel auf Sommerräder 2025",
        counterparty_name="Garage Sihltal AG",
    ),
    _booking("BK-4", -40.0, "TWINT an Anna Meier «Znacht»", counterparty_name="Anna Meier"),
    _booking("BK-5", -25.0, "TWINT an Anna Meier «Kino»", counterparty_name="Anna Meier"),
]


@pytest.fixture
async def customer(client: httpx2.AsyncClient, apertus: FakeApertus) -> httpx2.AsyncClient:
    app.state.banking = _bank_client(bookings_by_token={"customer-token": ("CUST-009", BOOKINGS)})

    def answer(request_body: dict[str, Any]) -> str:
        rows = _rows_of(request_body=request_body)
        return json.dumps(
            {
                "rows": [
                    {
                        "ref": ref,
                        "category": "restaurants" if "Znacht" in row["text"] else "transport",
                        "certainty": "high",
                    }
                    for ref, row in rows.items()
                ]
            }
        )

    apertus.structured_reply = answer
    return client


async def test_copies_of_one_booking_get_one_answer_and_the_same_category(
    customer: httpx2.AsyncClient, apertus: FakeApertus, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = await _categorise_only(api=customer, monkeypatch=monkeypatch)

    (request,) = apertus.requests
    sent = sorted(row["text"] for row in _rows_of(request_body=request).values())
    # The yearly service goes once, as its newest copy; each TWINT message is its own booking.
    assert sent == [
        "TWINT an Anna Meier «Kino»",
        "TWINT an Anna Meier «Znacht»",
        "Zahlung QR-Rechnung Garage Sihltal AG, Jahresservice VW Golf 2025",
        "Zahlung QR-Rechnung Garage Sihltal AG, Radwechsel auf Sommerräder 2025",
    ]
    assert run["tagged_by_model"] == 5
    tags = await _tags(api=customer)
    assert tags["BK-1"]["category"] == tags["BK-2"]["category"] == "transport"
    assert tags["BK-4"]["category"] == "restaurants"
    assert tags["BK-5"]["category"] == "transport"
