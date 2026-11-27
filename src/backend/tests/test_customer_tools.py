from datetime import date
from typing import Any
from uuid import uuid4

import httpx2
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.context_entries.repository import ContextEntryRepository
from app.features.context_entries.schemas import RequestContextEntryCreate
from app.features.documents.repository import DocumentRepository
from app.features.documents.schemas import LIST_MAX_CHARS
from app.features.documents.service import DocumentService
from app.features.tool_calls.schemas import ToolDecision, ToolRequest
from tests.conftest import FakeApertus, fake_banking_client, fake_ocr_client
from tests.factories import DEMO_USER_ID, make_conversation
from tests.test_documents_service import ScriptedApertus

PAYSLIP = "Lohnabrechnung_2026-11_Lukas_Meier.pdf"
NET_PAY = {"name": "net_pay", "amount": 8742.35, "currency": "CHF", "passage": "Nettolohn 8'742.35"}
GOAL = {"kind": "goal", "text": "Japan trip in 2027", "amount_chf": 12000}


async def _store_document(session: AsyncSession, name: str, **fields: Any) -> None:
    await DocumentRepository(session=session).create(
        banking_document_id="DOC-0001", name=name, markdown="Nettolohn 8'742.35", **fields
    )


def _calls(*tools: str) -> str:
    requests = [ToolRequest(reason="Needs it.", tool=tool, arguments={}) for tool in tools]
    return ToolDecision(plan="Look it up.", calls=requests).model_dump_json()


async def test_the_chat_reads_documents_and_entries_only_through_tools(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    await _store_document(
        session=session,
        name=PAYSLIP,
        owner_id=DEMO_USER_ID,
        kind="payslip",
        title="Lohnabrechnung November 2026",
        document_date=date(2026, 11, 25),
        fields=[NET_PAY],
    )
    await _store_document(session=session, name="Someone_else.pdf", owner_id=uuid4())
    assert (await client.post("/api/context-entries", json=GOAL)).status_code == 201
    await ContextEntryRepository(session=session).create(
        data=RequestContextEntryCreate(kind="fact", text="Someone else's fact"),
        owner_id=uuid4(),
        status="active",
        source="customer",
    )
    apertus.decisions = [_calls("list_documents", "list_context_entries")]
    apertus.reply = "Your net pay was CHF 8'742.35."
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"

    response = await client.post(f"{url}/messages", json={"content": "Who am I?"})

    assert response.status_code == 201
    question = apertus.requests[0]["messages"][-2]["content"]
    assert question.endswith("Who am I?")
    for private in (PAYSLIP, "8742.35", "Japan", "employer", "<customer>"):
        assert private not in question
    calls = {call["tool_name"]: call for call in (await client.get(f"{url}/tool-calls")).json()}
    documents = calls["list_documents"]["result"]
    assert [document["name"] for document in documents["documents"]] == [PAYSLIP]
    assert documents["documents"][0]["fields"][0]["amount"] == 8742.35
    assert documents["left_out"] == 0
    entries = calls["list_context_entries"]["result"]["entries"]
    assert [entry["text"] for entry in entries] == ["Japan trip in 2027"]
    checks = {check["name"]: check for check in response.json()["provenance"]["checks"]}
    assert checks["figures_found"]["passed"], checks["figures_found"]


async def test_the_oldest_documents_are_left_out_when_the_list_is_full(
    session: AsyncSession,
) -> None:
    for number in range(30):
        await _store_document(
            session=session, name=f"doc-{number:02}.pdf", owner_id=DEMO_USER_ID, title="x" * 200
        )
    service = DocumentService(
        documents=DocumentRepository(session=session),
        banking=fake_banking_client(),
        ocr=fake_ocr_client(),
        apertus=ScriptedApertus(session=session, answers=[]).client(),
    )

    listing = await service.list_summaries(owner_id=DEMO_USER_ID)

    assert 0 < len(listing.documents) < 30
    assert listing.left_out == 30 - len(listing.documents)
    assert sum(len(document.model_dump_json()) for document in listing.documents) <= LIST_MAX_CHARS
    assert listing.documents[0].name == "doc-29.pdf"
