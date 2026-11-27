import json
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import httpx2
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.apertus import ApertusClient
from app.core.config import get_settings
from app.features.documents.repository import DocumentRepository
from app.features.documents.schemas import DocumentDescription, ResponseDocument
from app.features.documents.service import DocumentService
from tests.conftest import (
    CUSTOMER_TOKEN,
    FAKE_USAGE,
    FakeApertus,
    fake_banking_client,
    fake_ocr_client,
)

PAYSLIP = """## Lohnabrechnung November 2026

| Lohnart          | Betrag CHF   |
|------------------|--------------|
| Bruttolohn       | 10'269.23    |
| Nettolohn        | 8'742.35     |
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

    def client(self) -> ApertusClient:
        def handle(request: httpx2.Request) -> httpx2.Response:
            self.requests.append(json.loads(request.content))
            self.in_transaction.append(self.session.in_transaction())
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
    assert document["provenance"] is None
    assert (await client.get("/api/documents")).json() == [document]
