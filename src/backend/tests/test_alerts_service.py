from datetime import date
from typing import Any

import httpx2
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import owner_id
from app.features.documents.repository import DocumentRepository
from tests.conftest import CUSTOMER_ID


async def _bill(
    session: AsyncSession,
    amount: float | None,
    payee: str = "Zahnarztpraxis Dr. Keller",
    kind: str = "reminder",
    document_date: date | None = date(2026, 11, 1),
    currency: str | None = "CHF",
    name: str = "Mahnung_Keller.pdf",
    issuer: str | None = None,
) -> str:
    fields: list[dict[str, Any]] = [
        {"name": "payee", "text": payee, "passage": payee},
        {"name": "due_date", "date": "2026-11-30", "passage": "zahlbar bis 30.11.2026"},
    ]
    if amount is not None:
        fields.append(
            {"name": "amount_due", "amount": amount, "currency": currency, "passage": f"{amount}"}
        )
    document = await DocumentRepository(session=session).create(
        owner_id=owner_id(customer_id=CUSTOMER_ID),
        banking_document_id="DOC-0001",
        name=name,
        markdown="",
        kind=kind,
        issuer=payee if issuer is None else issuer,
        document_date=document_date,
        fields=fields,
    )
    return str(document.id)


async def _alerts(client: httpx2.AsyncClient) -> list[dict[str, Any]]:
    response = await client.get("/api/alerts")
    assert response.status_code == 200
    return response.json()


async def test_an_unpaid_reminder_shows_with_its_document_and_figures(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    document_id = await _bill(session=session, amount=385.0)

    alerts = await _alerts(client=client)

    assert alerts == [
        {
            "key": f"invoice:{document_id}",
            "kind": "invoice",
            "document_id": document_id,
            "document_name": "Mahnung_Keller.pdf",
            "document_kind": "reminder",
            "payee": "Zahnarztpraxis Dr. Keller",
            "amount_chf": "385.00",
            "due_date": "2026-11-30",
            "document_date": "2026-11-01",
        }
    ]


async def test_a_booking_of_the_amount_after_the_document_pays_it(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    # The fake bank books CHF 212.10 to Migros on 30 October.
    await _bill(session=session, amount=212.08, payee="Migros", document_date=date(2026, 10, 20))

    assert await _alerts(client=client) == []


async def test_a_booking_of_the_amount_before_the_document_does_not_pay_it(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    await _bill(session=session, amount=212.10, payee="Migros", document_date=date(2026, 11, 1))

    assert len(await _alerts(client=client)) == 1


async def test_an_amount_six_rappen_off_does_not_pay_it(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    await _bill(session=session, amount=212.16, payee="Migros", document_date=date(2026, 10, 20))

    assert len(await _alerts(client=client)) == 1


async def test_a_pending_payment_of_the_amount_covers_it(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    # The fake bank lists a pending payment of CHF 168.25 to EKZ.
    await _bill(session=session, amount=168.25, payee="EKZ", kind="invoice")

    assert await _alerts(client=client) == []


async def test_an_invoice_and_its_reminder_show_once_as_the_reminder(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    await _bill(session=session, amount=385.0, kind="invoice", name="Rechnung_Keller.pdf")
    await _bill(session=session, amount=385.0, kind="reminder", name="Mahnung_Keller.pdf")

    alerts = await _alerts(client=client)

    assert [alert["document_name"] for alert in alerts] == ["Mahnung_Keller.pdf"]


async def test_a_bill_without_an_amount_or_in_euro_shows_nothing(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    await _bill(session=session, amount=None)
    await _bill(session=session, amount=120.0, currency="EUR", payee="Hotel Adler")

    assert await _alerts(client=client) == []


async def test_a_done_flag_stays_hidden_and_a_second_done_returns_the_first(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    document_id = await _bill(session=session, amount=385.0)
    key = f"invoice:{document_id}"

    first = await client.post("/api/alert-dismissals", json={"key": key})
    second = await client.post("/api/alert-dismissals", json={"key": key})

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert await _alerts(client=client) == []

    deleted = await client.delete(f"/api/alert-dismissals/{first.json()['id']}")
    assert deleted.status_code == 204
    assert len(await _alerts(client=client)) == 1


async def test_a_turned_off_check_shows_nothing_until_it_is_reset(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    await _bill(session=session, amount=385.0)

    assert (await client.get("/api/alert-settings")).json() == [
        {"kind": "invoice", "enabled": True}
    ]
    off = await client.patch("/api/alert-settings/invoice", json={"enabled": False})
    assert off.json() == {"kind": "invoice", "enabled": False}
    assert await _alerts(client=client) == []

    reset = await client.delete("/api/alert-settings/invoice")
    assert reset.status_code == 204
    assert len(await _alerts(client=client)) == 1


async def test_a_dismissal_that_is_not_yours_is_not_found(client: httpx2.AsyncClient) -> None:
    created = await client.post("/api/alert-dismissals", json={"key": "invoice:x"})
    other = "00000000-0000-0000-0000-000000000000"

    assert (await client.delete(f"/api/alert-dismissals/{other}")).status_code == 404
    assert created.status_code == 201


async def test_the_alert_names_the_issuer_not_the_payee_address(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    await _bill(
        session=session,
        amount=440.0,
        payee="Zahnarztpraxis Neuwiesen Neuwiesenstrasse 20 8400 Winterthur",
        issuer="Zahnarztpraxis Neuwiesen",
    )

    assert [alert["payee"] for alert in await _alerts(client=client)] == [
        "Zahnarztpraxis Neuwiesen"
    ]
