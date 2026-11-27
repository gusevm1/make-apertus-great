import json
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import httpx2
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.apertus import ApertusClient
from app.clients.banking import BankingClient
from app.core.auth import owner_id
from app.core.config import get_settings
from app.features.documents.repository import DocumentRepository
from app.features.documents.schemas import (
    DESCRIBE_TIMEOUT_SECONDS,
    Document,
    DocumentDescription,
    ResponseDocument,
)
from app.features.documents.service import DocumentService
from app.main import app
from tests.conftest import (
    CUSTOMER_ID,
    CUSTOMER_TOKEN,
    FAKE_USAGE,
    TODAY,
    FakeApertus,
    fake_banking_client,
    fake_ocr_client,
)

PAYSLIP = """## Lohnabrechnung November 2026

| Lohnart          | Betrag CHF   | Jan-Nov CHF   |
|------------------|--------------|---------------|
| Bruttolohn       | 10'269.23    | 119'985.91    |
| Nettolohn        | 8'742.35     | 102'645.85    |
"""
MONTH = {"name": "month", "date": "2026-11-15", "passage": "Lohnabrechnung November 2026"}
GROSS = {
    "name": "gross_pay",
    "amount": 10269.23,
    "currency": "CHF",
    "passage": "Bruttolohn 10'269.23",
}
NET = {
    "name": "net_pay",
    "amount": 8742.35,
    "currency": "CHF",
    "passage": "| Nettolohn | 8'742.35 |",
}
INVENTED_GROSS = {**GROSS, "passage": "Bruttolohn 11'000.00"}


def _payslip(*fields: dict[str, Any]) -> str:
    return json.dumps(
        {
            "kind": "payslip",
            "title": "Lohnabrechnung November 2026",
            "issuer": "Helvetia Digital AG",
            "document_date": "2026-11-20",
            "summary": "Lohn für November 2026.",
            "fields": list(fields),
        }
    )


@dataclass
class ScriptedApertus:
    """Apertus faked at the HTTP level: answers in order and notes if a transaction was open."""

    session: AsyncSession
    answers: list[str]
    status: int = 200
    requests: list[dict[str, Any]] = field(default_factory=list)
    in_transaction: list[bool] = field(default_factory=list)
    read_timeouts: list[float] = field(default_factory=list)

    def client(self) -> ApertusClient:
        def handle(request: httpx2.Request) -> httpx2.Response:
            self.requests.append(json.loads(request.content))
            self.in_transaction.append(self.session.in_transaction())
            self.read_timeouts.append(request.extensions["timeout"]["read"])
            if self.status != 200:
                return httpx2.Response(self.status, json={"error": {"message": "fake failure"}})
            message = {"role": "assistant", "content": self.answers.pop(0)}
            choice = {"index": 0, "finish_reason": "stop", "message": message}
            return httpx2.Response(200, json={"choices": [choice], "usage": FAKE_USAGE})

        fake_http = httpx2.AsyncClient(transport=httpx2.MockTransport(handle))
        return ApertusClient(settings=get_settings(), http_client=fake_http)


async def _upload(session: AsyncSession, apertus: ScriptedApertus) -> ResponseDocument:
    service = DocumentService(
        documents=DocumentRepository(session=session),
        banking=fake_banking_client(),
        ocr=fake_ocr_client(markdown=PAYSLIP),
        apertus=apertus.client(),
    )
    document = await service.create_document(
        content=b"%PDF-1.7 fake",
        name="Lohnabrechnung.pdf",
        content_type="application/pdf",
        owner_id=uuid4(),
        token=CUSTOMER_TOKEN,
    )
    stored = await DocumentRepository(session=session).get_by_id(entity_id=document.id)
    assert stored == document
    return ResponseDocument.model_validate(document, from_attributes=True)


async def test_a_payslip_is_described_with_its_fields_and_passages(session: AsyncSession) -> None:
    apertus = ScriptedApertus(session=session, answers=[_payslip(MONTH, GROSS, NET)])

    document = await _upload(session=session, apertus=apertus)

    assert document.kind == "payslip"
    assert document.title == "Lohnabrechnung November 2026"
    fields = {field.name: field for field in document.fields}
    assert str(fields["month"].date) == "2026-11-01"
    assert fields["gross_pay"].amount == 10269.23
    assert fields["net_pay"].passage == "| Nettolohn | 8'742.35 |"
    assert document.provenance is not None
    assert document.provenance.model == "fake-smart"
    assert [check.model_dump() for check in document.provenance.checks] == [
        {"name": "fields_in_text", "passed": True, "detail": None}
    ]
    assert len(apertus.requests) == 1
    assert apertus.in_transaction == [False]
    assert apertus.read_timeouts == [DESCRIBE_TIMEOUT_SECONDS]


async def test_a_description_invalid_twice_names_its_error_in_the_provenance(
    session: AsyncSession,
) -> None:
    unknown_kind = json.dumps({"kind": "letter", "summary": "Ein Brief."})
    apertus = ScriptedApertus(session=session, answers=[unknown_kind, unknown_kind])

    document = await _upload(session=session, apertus=apertus)

    assert document.kind is None
    assert document.provenance is not None
    assert document.provenance.model == "fake-smart"
    [check] = document.provenance.checks
    assert check.name == "described"
    assert check.passed is False
    assert check.detail is not None
    assert check.detail.startswith(
        "Model returned invalid DocumentDescription twice, last: kind: Input should be"
    )
    assert "letter" not in check.detail
    assert len(apertus.requests) == 2


async def test_a_field_not_in_the_text_is_asked_for_once_and_then_dropped(
    session: AsyncSession,
) -> None:
    apertus = ScriptedApertus(
        session=session, answers=[_payslip(INVENTED_GROSS, NET), _payslip(INVENTED_GROSS, NET)]
    )

    document = await _upload(session=session, apertus=apertus)

    assert [field.name for field in document.fields] == ["net_pay"]
    assert len(apertus.requests) == 2
    correction = apertus.requests[1]["messages"][-2]["content"]
    assert 'gross_pay: "Bruttolohn 11\'000.00": these words are not in the document' in correction
    assert "net_pay" not in correction
    assert document.provenance is not None
    check = document.provenance.checks[0]
    assert check.passed is False
    assert check.detail == (
        'dropped gross_pay: "Bruttolohn 11\'000.00": these words are not in the document'
    )
    assert apertus.in_transaction == [False, False]


async def test_a_field_without_a_value_is_asked_for_again(session: AsyncSession) -> None:
    without_value = {"name": "net_pay", "passage": "Nettolohn 8'742.35"}
    apertus = ScriptedApertus(
        session=session, answers=[_payslip(without_value), _payslip(without_value)]
    )

    document = await _upload(session=session, apertus=apertus)

    assert document.fields == []
    assert len(apertus.requests) == 2


async def test_a_passage_that_cuts_a_number_short_fails(session: AsyncSession) -> None:
    rounded = {**NET, "amount": 8742, "passage": "Nettolohn 8'742"}
    apertus = ScriptedApertus(session=session, answers=[_payslip(rounded), _payslip(rounded)])

    document = await _upload(session=session, apertus=apertus)

    assert document.fields == []
    assert len(apertus.requests) == 2


async def test_a_corrected_field_is_kept(session: AsyncSession) -> None:
    wrong_amount = {**GROSS, "amount": 10296.23}
    apertus = ScriptedApertus(session=session, answers=[_payslip(wrong_amount), _payslip(GROSS)])

    document = await _upload(session=session, apertus=apertus)

    assert [field.amount for field in document.fields] == [10269.23]
    correction = apertus.requests[1]["messages"][-2]["content"]
    assert 'gross_pay: "Bruttolohn 10\'269.23": the amount is not in these words' in correction
    assert document.provenance is not None
    assert document.provenance.checks[0].passed is True


async def test_values_the_document_lacks_stay_empty(session: AsyncSession) -> None:
    assert "required" not in json.dumps(DocumentDescription.model_json_schema())
    absent = {"name": "gross_pay", "passage": ""}
    apertus = ScriptedApertus(session=session, answers=[_payslip(NET, absent)])

    document = await _upload(session=session, apertus=apertus)

    assert [field.name for field in document.fields] == ["net_pay"]
    assert len(apertus.requests) == 1


async def test_an_upload_stands_without_a_description_when_apertus_fails(
    client: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    apertus.status = 500

    uploaded = await client.post(
        "/api/documents", files={"file": ("Lohn.pdf", b"%PDF-1.7 fake", "application/pdf")}
    )

    assert uploaded.status_code == 201
    document = uploaded.json()
    assert len(apertus.requests) == 1
    assert document["kind"] is None
    assert document["summary"] is None
    assert document["fields"] == []
    assert document["provenance"]["checks"] == [
        {"name": "described", "passed": False, "detail": "Apertus returned 500"}
    ]
    assert (await client.get("/api/documents")).json() == [document]


@dataclass
class DeletingBank:
    """The banking API faked at the HTTP level for deletes: notes each one, answers `status`."""

    status: int = 204
    deletes: list[httpx2.Request] = field(default_factory=list)

    def client(self) -> BankingClient:
        def handle(request: httpx2.Request) -> httpx2.Response:
            if request.url.path == "/api/system/info":
                return httpx2.Response(200, json={"today": TODAY.isoformat()})
            if request.headers.get("authorization") != f"Bearer {CUSTOMER_TOKEN}":
                return httpx2.Response(401, json={"detail": "Not authenticated"})
            if request.url.path == "/api/customer":
                return httpx2.Response(200, json={"customer_id": CUSTOMER_ID})
            if request.method == "DELETE":
                self.deletes.append(request)
                return httpx2.Response(self.status, json={"detail": "Not found"})
            return httpx2.Response(500)

        fake_http = httpx2.AsyncClient(
            transport=httpx2.MockTransport(handle), base_url=get_settings().banking_api_url
        )
        return BankingClient(settings=get_settings(), http_client=fake_http)


@pytest.fixture
def bank(client: httpx2.AsyncClient) -> DeletingBank:
    bank = DeletingBank()
    app.state.banking = bank.client()
    return bank


async def _stored(session: AsyncSession, customer_id: str = CUSTOMER_ID) -> Document:
    return await DocumentRepository(session=session).create(
        owner_id=owner_id(customer_id=customer_id),
        banking_document_id="DOC-0007",
        name="Lohnabrechnung.pdf",
        markdown=PAYSLIP,
    )


async def test_a_deleted_document_is_gone_here_and_in_the_bank(
    client: httpx2.AsyncClient, session: AsyncSession, bank: DeletingBank
) -> None:
    document = await _stored(session=session)

    deleted = await client.delete(f"/api/documents/{document.id}")

    assert deleted.status_code == 204
    assert (await client.get("/api/documents")).json() == []
    assert [(request.url.path, request.headers["authorization"]) for request in bank.deletes] == [
        ("/api/documents/DOC-0007", f"Bearer {CUSTOMER_TOKEN}")
    ]


async def test_a_file_the_bank_no_longer_has_still_removes_our_row(
    client: httpx2.AsyncClient, session: AsyncSession, bank: DeletingBank
) -> None:
    bank.status = 404
    document = await _stored(session=session)

    deleted = await client.delete(f"/api/documents/{document.id}")

    assert deleted.status_code == 204
    assert await DocumentRepository(session=session).get_by_id(entity_id=document.id) is None


async def test_a_bank_failure_keeps_our_row(
    client: httpx2.AsyncClient, session: AsyncSession, bank: DeletingBank
) -> None:
    bank.status = 500
    document = await _stored(session=session)

    deleted = await client.delete(f"/api/documents/{document.id}")

    assert deleted.status_code == 502
    assert await DocumentRepository(session=session).get_by_id(entity_id=document.id) is not None


async def test_another_customers_document_is_not_deleted(
    client: httpx2.AsyncClient, session: AsyncSession, bank: DeletingBank
) -> None:
    foreign = await _stored(session=session, customer_id="CUST-002")

    deleted = await client.delete(f"/api/documents/{foreign.id}")

    assert deleted.status_code == 404
    assert bank.deletes == []
    assert await DocumentRepository(session=session).get_by_id(entity_id=foreign.id) is not None


async def test_messages_keep_a_deleted_documents_name_and_a_new_one_cannot_send_it(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    document = await _stored(session=session)
    conversation = (await client.post("/api/conversations", json={})).json()
    url = f"/api/conversations/{conversation['id']}/messages"
    question = {"content": "Wie hoch ist mein Nettolohn?", "document_ids": [str(document.id)]}
    assert (await client.post(url, json=question)).status_code == 201
    app.state.banking = DeletingBank().client()

    assert (await client.delete(f"/api/documents/{document.id}")).status_code == 204

    stored_question, _ = (await client.get(url)).json()
    assert stored_question["documents"] == [{"id": str(document.id), "name": "Lohnabrechnung.pdf"}]
    assert (await client.post(url, json=question)).status_code == 404
