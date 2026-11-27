from datetime import date
from typing import Any
from uuid import uuid4

import httpx2
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.context_entries import tools as context_entry_tools
from app.features.context_entries.repository import ContextEntryRepository
from app.features.context_entries.schemas import (
    ACTIVE_ENTRIES_MAX,
    TEXT_MAX_LENGTH,
    ContextEntryList,
    RequestContextEntryCreate,
)
from app.features.context_entries.service import ContextEntryService
from app.features.documents import tools as document_tools
from app.features.documents.repository import DocumentRepository
from app.features.documents.schemas import LIST_MAX_CHARS, DocumentList
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


def _document_service(session: AsyncSession) -> DocumentService:
    return DocumentService(
        documents=DocumentRepository(session=session),
        banking=fake_banking_client(),
        ocr=fake_ocr_client(),
        apertus=ScriptedApertus(session=session, answers=[]).client(),
    )


async def test_the_oldest_documents_are_left_out_when_the_list_is_full(
    session: AsyncSession,
) -> None:
    for number in range(30):
        await _store_document(
            session=session, name=f"doc-{number:02}.pdf", owner_id=DEMO_USER_ID, title="x" * 200
        )
    service = _document_service(session=session)
    (tool, _) = document_tools.get_tools(service=service, owner_id=DEMO_USER_ID)
    assert tool.handler is not None

    listing = await tool.handler(tool.args_schema())

    assert isinstance(listing, DocumentList)
    assert 0 < len(listing.documents) < 30
    assert listing.left_out == 30 - len(listing.documents)
    assert sum(len(document.model_dump_json()) for document in listing.documents) <= LIST_MAX_CHARS
    assert listing.documents[0].name == "doc-29.pdf"
    assert listing.note is not None and f"{listing.left_out} older documents" in listing.note


async def _entry_service(session: AsyncSession, texts: list[str]) -> ContextEntryService:
    repository = ContextEntryRepository(session=session)
    for text in texts:
        await repository.create(
            data=RequestContextEntryCreate(kind="fact", text=text),
            owner_id=DEMO_USER_ID,
            status="active",
            source="customer",
        )
    return ContextEntryService(entries=repository)


async def test_the_oldest_entries_are_left_out_when_the_list_is_full(
    session: AsyncSession,
) -> None:
    texts = [f"{number:02} " + "x" * (TEXT_MAX_LENGTH - 3) for number in range(ACTIVE_ENTRIES_MAX)]
    service = await _entry_service(session=session, texts=texts)

    listing = await service.list_summaries(owner_id=DEMO_USER_ID, text=None)

    assert len(listing.model_dump_json()) < 6000
    assert listing.left_out > 0
    assert listing.left_out == ACTIVE_ENTRIES_MAX - len(listing.entries)
    assert listing.entries[0].text.startswith(f"{ACTIVE_ENTRIES_MAX - 1:02} ")
    for private in ("owner_id", "source_id", "replaced_by_id", "replaces_id"):
        assert private not in listing.model_dump()["entries"][0]


async def test_a_few_short_entries_all_come_back(session: AsyncSession) -> None:
    service = await _entry_service(session=session, texts=["Rent is due monthly", "Likes trains"])

    listing = await service.list_summaries(owner_id=DEMO_USER_ID, text=None)

    assert [entry.text for entry in listing.entries] == ["Likes trains", "Rent is due monthly"]
    assert listing.left_out == 0


async def test_a_search_finds_an_old_entry_the_full_list_leaves_out(session: AsyncSession) -> None:
    filler = "x" * (TEXT_MAX_LENGTH - 6)
    texts = ["Velo-Ferien in Norwegen 2028", *(f"{n:02} in {filler}" for n in range(49))]
    service = await _entry_service(session=session, texts=texts)
    await ContextEntryRepository(session=session).create(
        data=RequestContextEntryCreate(kind="goal", text="Someone else in Norwegen"),
        owner_id=uuid4(),
        status="active",
        source="customer",
    )
    (tool,) = context_entry_tools.get_tools(service=service, owner_id=DEMO_USER_ID)
    assert tool.handler is not None

    newest = await tool.handler(tool.args_schema())
    # "in" matches every entry; the one holding the most words still comes first.
    found = await tool.handler(tool.args_schema(text="Ferien in NORWEGEN"))

    assert isinstance(newest, ContextEntryList) and isinstance(found, ContextEntryList)
    assert "Norwegen" not in newest.model_dump_json()
    assert newest.note is not None and f"{newest.left_out} older entries" in newest.note
    assert found.entries[0].text == "Velo-Ferien in Norwegen 2028"
    assert "Someone else in Norwegen" not in found.model_dump_json()


async def test_a_document_search_matches_the_issuer_and_escapes_wildcards(
    session: AsyncSession,
) -> None:
    await _store_document(
        session=session, name="Police.pdf", owner_id=DEMO_USER_ID, issuer="Helsana"
    )
    await _store_document(session=session, name="Lohn.pdf", owner_id=DEMO_USER_ID, title="Lohn")
    service = _document_service(session=session)

    helsana = await service.list_summaries(owner_id=DEMO_USER_ID, text="helsana")
    wildcard = await service.list_summaries(owner_id=DEMO_USER_ID, text="%")

    assert [document.name for document in helsana.documents] == ["Police.pdf"]
    assert wildcard.documents == []
